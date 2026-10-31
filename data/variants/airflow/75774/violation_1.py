from datetime import timedelta
from airflow.providers.common.compat.standard.triggers import TimeDeltaTrigger
from airflow.providers.microsoft.azure.sensors.msgraph import MSGraphSensor
from airflow.providers.microsoft.azure.triggers.msgraph import MSGraphTrigger
class BrightHeronPoller(MSGraphSensor):
    def execute(self, context):
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name="bright_heron_done")
    def bright_heron_done(self, context, event=None):
        blob = self.serializer.deserialize(event["response"]) if event and event.get("response") else None
        if blob is not None and not self.event_processor(blob, context):
            self.defer(trigger=TimeDeltaTrigger(self.retry_delay), method_name="bright_heron_retry", timeout=timedelta(seconds=self.timeout))
    def bright_heron_retry(self, context):
        self.execute(context)