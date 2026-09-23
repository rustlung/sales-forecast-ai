from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.orm import Session,sessionmaker
from sales_forecast.config.settings import Settings
from sales_forecast.database.models import AnalysisRun,Forecast
from sales_forecast.repositories.analysis_runs import AnalysisRunRepository
from sales_forecast.repositories.datasets import DatasetRepository
from sales_forecast.ai.insights import ProxyAIClient,compact_payload,AIInsightsError
class AIInsightsService:
 def __init__(self,factory:sessionmaker[Session],settings:Settings): self.factory,self.settings=factory,settings;self.datasets=DatasetRepository();self.runs=AnalysisRunRepository()
 def generate(self,dataset_id:int,target:str="revenue"):
  with self.factory() as s:
   self.datasets.get_by_id(s,dataset_id)
   desc=s.scalar(select(AnalysisRun).where(AnalysisRun.dataset_id==dataset_id,AnalysisRun.analysis_type=="descriptive",AnalysisRun.status=="completed").order_by(AnalysisRun.created_at.desc()))
   forecast=s.scalar(select(Forecast).where(Forecast.dataset_id==dataset_id,Forecast.target==target).order_by(Forecast.created_at.desc()))
   scenario=s.scalar(select(AnalysisRun).where(AnalysisRun.dataset_id==dataset_id,AnalysisRun.analysis_type=="scenario",AnalysisRun.status=="completed").order_by(AnalysisRun.created_at.desc()))
  if not desc: raise AIInsightsError("Completed descriptive analysis is required")
  if not forecast: raise AIInsightsError("Completed forecast is required")
  with self.factory() as s:
   with s.begin(): run=self.runs.create_running(s,dataset_id,"ai_insights");run_id=run.id
  try:
   payload=compact_payload(desc.result_json or {},forecast.forecast_json,scenario.result_json if scenario else None); answer=ProxyAIClient(self.settings.openai_api_key,self.settings.openai_base_url,self.settings.openai_model).generate(payload)
   result={"input_payload":payload,"ai_result":answer.model_dump(),"model_name":self.settings.openai_model}
   with self.factory() as s:
    with s.begin(): self.runs.complete(s,run_id,result)
   return run_id,answer
  except AIInsightsError as error:
   with self.factory() as s:
    with s.begin(): self.runs.fail(s,run_id,str(error))
   raise
  except Exception:
   with self.factory() as s:
    with s.begin(): self.runs.fail(s,run_id,"AI insights generation failed. Check configuration and application logs.")
   raise
