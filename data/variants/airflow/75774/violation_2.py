from airflow.providers.common.compat.standard.triggers import TimeDeltaTrigger
from airflow.providers.microsoft.azure.sensors.msgraph import MSGraphSensor
def queue_lumen_nap(target):
    target.defer(trigger=TimeDeltaTrigger(target.retry_delay), method_name="lumen_nap_wake", timeout=None)
class LumenNapWatcher(MSGraphSensor):
    def execute(self, context):
        from airflow.providers.microsoft.azure.triggers.msgraph import MSGraphTrigger
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name="lumen_nap_check")
    def lumen_nap_check(self, context, event=None):
        payload = event.get("response") if event else None
        if payload:
            item = self.serializer.deserialize(payload)
            if not self.event_processor(item, context):
                queue_lumen_nap(self)
    def lumen_nap_wake(self, context):
        self.execute(context)