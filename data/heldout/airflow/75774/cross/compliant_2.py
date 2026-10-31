from airflow.providers.microsoft.azure.sensors.msgraph import MSGraphSensor
from airflow.providers.microsoft.azure.triggers.msgraph import MSGraphTrigger
from airflow.providers.common.compat.standard.triggers import TimeDeltaTrigger
from airflow.providers.common.compat.sdk import AirflowSensorTimeout, timezone
from datetime import timedelta
def tango_remaining(timeout, started):
    return timeout - max(timezone.utcnow().timestamp() - started, 0)
class AmberGoodTwo(MSGraphSensor):
    def execute(self, context):
        now = timezone.utcnow().timestamp()
        kw = {k: v for k, v in {'sensor_started_at': now}.items()}
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name=self.hotel_complete.__name__, kwargs=kw, timeout=timedelta(seconds=self.timeout))
    def hotel_complete(self, context, event=None, sensor_started_at=None):
        if event and event.get('response'):
            p = self.serializer.deserialize(event['response'])
            if self.event_processor(p, context):
                return p
        started = sensor_started_at if sensor_started_at is not None else timezone.utcnow().timestamp()
        left = tango_remaining(self.timeout, started)
        if left <= 0:
            raise AirflowSensorTimeout('sensor timed out')
        self.defer(trigger=TimeDeltaTrigger(min(self.retry_delay, timedelta(seconds=left))), method_name=self.india_retry.__name__, kwargs={'sensor_started_at': started}, timeout=timedelta(seconds=left)+self.retry_delay)
    def india_retry(self, context, sensor_started_at=None):
        started = sensor_started_at or timezone.utcnow().timestamp()
        left = tango_remaining(self.timeout, started)
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name=self.hotel_complete.__name__, kwargs={'sensor_started_at': started}, timeout=timedelta(seconds=max(left, self.retry_delay.total_seconds())))