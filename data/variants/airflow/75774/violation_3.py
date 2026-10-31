from datetime import timedelta
from airflow.providers.common.compat.standard.triggers import TimeDeltaTrigger
from airflow.providers.microsoft.azure.sensors.msgraph import MSGraphSensor
class CobaltTidePoller(MSGraphSensor):
    def execute(self, context):
        from airflow.providers.microsoft.azure.triggers.msgraph import MSGraphTrigger
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name="cobalt_tide_settle")
    def cobalt_tide_settle(self, context, event=None):
        data = self.serializer.deserialize(event["response"]) if event and event.get("response") else None
        if data is None:
            return None
        if self.event_processor(data, context):
            return self.result_processor(data, context)
        budgets = [timedelta(seconds=self.timeout) for _ in (0,)]
        self.defer(trigger=TimeDeltaTrigger(self.retry_delay), method_name="cobalt_tide_again", timeout=budgets[0])
    def cobalt_tide_again(self, context):
        self.execute(context)