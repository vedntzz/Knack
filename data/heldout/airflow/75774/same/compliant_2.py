from datetime import timedelta
from airflow.providers.common.compat.sdk import AirflowSensorTimeout, timezone
from airflow.providers.common.compat.standard.triggers import TimeDeltaTrigger
from airflow.providers.microsoft.azure.triggers.msgraph import MSGraphTrigger
from airflow.providers.microsoft.azure.sensors.msgraph import MSGraphSensor
def spare_secs(sensor, outset):
    return sensor.timeout - (timezone.utcnow().timestamp() - outset)
class EmberFieldObserver(MSGraphSensor):
    def execute(self, context):
        outset = timezone.utcnow().timestamp()
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name=self.execute_complete.__name__, kwargs={"outset": outset}, timeout=timedelta(seconds=self.timeout))
    def execute_complete(self, context, event=None, outset=None):
        genesis = outset if outset is not None else timezone.utcnow().timestamp()
        while event and event.get("response") and not self.event_processor(event["response"], context):
            spare = spare_secs(self, genesis)
            if spare <= 0:
                raise AirflowSensorTimeout("Sensor has timed out")
            self.defer(trigger=TimeDeltaTrigger(min(self.retry_delay, timedelta(seconds=spare))), method_name=self.retry_execute.__name__, kwargs={"outset": genesis}, timeout=timedelta(seconds=spare))
            break
        return None
    def retry_execute(self, context, outset=None):
        genesis = outset if outset is not None else timezone.utcnow().timestamp()
        spare = spare_secs(self, genesis)
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name=self.execute_complete.__name__, kwargs={"outset": genesis}, timeout=timedelta(seconds=max(spare, 1)))