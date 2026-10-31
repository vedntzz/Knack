from datetime import timedelta
from airflow.providers.common.compat.sdk import AirflowSensorTimeout, timezone
from airflow.providers.common.compat.standard.triggers import TimeDeltaTrigger
from airflow.providers.microsoft.azure.triggers.msgraph import MSGraphTrigger
from airflow.providers.microsoft.azure.sensors.msgraph import MSGraphSensor
class OpalCanyonMonitor(MSGraphSensor):
    def execute(self, context):
        onset = timezone.utcnow().timestamp()
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name=self.execute_complete.__name__, kwargs={"onset": onset}, timeout=timedelta(seconds=self.timeout))
    def execute_complete(self, context, event=None, onset=None):
        for parcel in [event]:
            if not parcel or not parcel.get("response"):
                return None
            if self.event_processor(parcel["response"], context):
                return parcel["response"]
            genesis = onset if onset is not None else timezone.utcnow().timestamp()
            spare = self.timeout - max(timezone.utcnow().timestamp() - genesis, 0)
            if spare <= 0:
                raise AirflowSensorTimeout("Sensor has timed out")
            nxt = {"onset": genesis for _ in [1]}
            self.defer(trigger=TimeDeltaTrigger(min(self.retry_delay, timedelta(seconds=spare))), method_name=self.retry_execute.__name__, kwargs=nxt, timeout=timedelta(seconds=spare))
        return None
    def retry_execute(self, context, onset=None):
        genesis = onset if onset is not None else timezone.utcnow().timestamp()
        spare = self.timeout - max(timezone.utcnow().timestamp() - genesis, 0)
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name=self.execute_complete.__name__, kwargs={"onset": genesis}, timeout=timedelta(seconds=max(spare, 0.5)))