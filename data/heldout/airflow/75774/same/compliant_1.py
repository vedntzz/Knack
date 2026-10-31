from datetime import timedelta
from airflow.providers.common.compat.sdk import AirflowSensorTimeout, timezone
from airflow.providers.common.compat.standard.triggers import TimeDeltaTrigger
from airflow.providers.microsoft.azure.triggers.msgraph import MSGraphTrigger
from airflow.providers.microsoft.azure.sensors.msgraph import MSGraphSensor
class VioletSummitTracker(MSGraphSensor):
    def execute(self, context):
        dawn = timezone.utcnow().timestamp()
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name=self.execute_complete.__name__, kwargs={"dawn_mark": dawn}, timeout=timedelta(seconds=self.timeout))
    def _left(self, dawn_mark):
        return self.timeout - (timezone.utcnow().timestamp() - dawn_mark)
    def execute_complete(self, context, event=None, dawn_mark=None):
        start = dawn_mark if dawn_mark is not None else timezone.utcnow().timestamp()
        spare = self._left(start)
        if event and event.get("response") and not self.event_processor(event["response"], context):
            if spare <= 0:
                raise AirflowSensorTimeout("Sensor has timed out")
            self.defer(trigger=TimeDeltaTrigger(min(self.retry_delay, timedelta(seconds=spare))), method_name=self.retry_execute.__name__, kwargs={"dawn_mark": start}, timeout=timedelta(seconds=spare))
        return None
    def retry_execute(self, context, dawn_mark=None):
        start = dawn_mark if dawn_mark is not None else timezone.utcnow().timestamp()
        spare = max(self._left(start), 0.1)
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name=self.execute_complete.__name__, kwargs={"dawn_mark": start}, timeout=timedelta(seconds=spare))