from __future__ import annotations
import argparse
from sales_forecast.config.settings import get_settings
from sales_forecast.database.session import create_engine,create_session_factory
from sales_forecast.logging_config import configure_logging
from sales_forecast.services.ai_insights import AIInsightsService
from sales_forecast.ai.insights import AIInsightsError
def main():
 p=argparse.ArgumentParser();p.add_argument("dataset_id",type=int);p.add_argument("--target",default="revenue",choices=("revenue","units_sold"));a=p.parse_args();settings=get_settings();configure_logging(settings.log_level)
 try: run,answer=AIInsightsService(create_session_factory(create_engine(settings.database_url)),settings).generate(a.dataset_id,a.target)
 except AIInsightsError as e: print(f"AI insights failed: {e}");raise SystemExit(2)
 print(f"analysis_run_id={run} model={settings.openai_model}\n{answer.summary}\nInsights: {'; '.join(answer.key_insights)}\nRecommendations: {'; '.join(answer.recommendations)}\nRisks: {'; '.join(answer.risks)}")
if __name__=="__main__":main()
