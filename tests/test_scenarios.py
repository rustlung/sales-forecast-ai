from datetime import date, timedelta
from decimal import Decimal
import json
import pytest
from sales_forecast.database.models import SalesRecord
from sales_forecast.scenarios.modeling import ScenarioInput, ScenarioValidationError, prepare_ml_frame, chronological_split, train_and_evaluate, predict

def records():
    return [SalesRecord(dataset_id=1,date=date(2025,1,1)+timedelta(days=i),product="A" if i%2 else "B",category="C",price=Decimal("10"),discount_pct=Decimal(i%10),ad_spend=Decimal("5"),promo=bool(i%2),units_sold=10,revenue=Decimal(str(100+i))) for i in range(100)]
def test_preparation_split_pipeline_and_prediction():
    frame=prepare_ml_frame(records()); train,test=chronological_split(frame)
    assert {"weekday","month","price","product"} <= set(frame.columns)
    assert set(train.date).isdisjoint(set(test.date))
    pipe, metrics, importance, _, _=train_and_evaluate(frame)
    value=predict(pipe,ScenarioInput("A","C",date(2025,5,1),10,5,10,False))
    assert value >= 0 and importance and json.dumps(metrics)
def test_validation():
    frame=prepare_ml_frame(records())
    with pytest.raises(ScenarioValidationError): ScenarioInput("A","C",date.today(),0,0,0,False).validate(frame)
    with pytest.raises(ScenarioValidationError): ScenarioInput("X","C",date.today(),1,0,0,False).validate(frame)
