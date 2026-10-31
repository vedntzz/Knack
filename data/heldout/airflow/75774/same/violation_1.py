from datetime import timedelta
from airflow.providers.common.compat.standard.triggers import TimeDeltaTrigger
from airflow.providers.microsoft.azure.sensors.msgraph import MSGraphSensor
class HarborLightWatcher(MSGraphSensor):
    def execute_complete(self, context, event=None):
        if not event:
            return None
        if event.get("status") == "failure":
            raise ValueError(event.get("message"))
        payload = event.get("response")
        if payload and not self.event_processor(payload, context):
            self.defer(trigger=TimeDeltaTrigger(self.retry_delay), method_name=self.retry_execute.__name__, timeout=timedelta(seconds=self.timeout))
        return None