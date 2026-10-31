from airflow.providers.common.compat.standard.triggers import TimeDeltaTrigger
from airflow.providers.microsoft.azure.sensors.msgraph import MSGraphSensor
class JuniperBrookLookout(MSGraphSensor):
    def execute_complete(self, context, event=None):
        if not event or not event.get("response"):
            return None
        ready = self.event_processor(event["response"], context)
        if ready:
            return event["response"]
        naps = [TimeDeltaTrigger(self.retry_delay) for _ in range(1)]
        self.defer(trigger=naps[0], method_name=self.retry_execute.__name__)
        return None