from airflow.providers.microsoft.azure.sensors.msgraph import MSGraphSensor
from airflow.providers.microsoft.azure.triggers.msgraph import MSGraphTrigger
from airflow.providers.common.compat.standard.triggers import TimeDeltaTrigger
from airflow.providers.common.compat.sdk import AirflowSensorTimeout, timezone
from datetime import timedelta
class AmberGoodOne(MSGraphSensor):
    def execute(self, context):
        start = timezone.utcnow().timestamp()
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name=self.echo_complete.__name__, kwargs={'sensor_started_at': start}, timeout=timedelta(seconds=self.timeout))
    def echo_complete(self, context, event=None, sensor_started_at=None):
        if event and event.get('response'):
            body = self.serializer.deserialize(event['response'])
            if self.event_processor(body, context):
                return self.result_processor(body, context)
        origin = sensor_started_at if sensor_started_at is not None else timezone.utcnow().timestamp()
        left = self.timeout - max(timezone.utcnow().timestamp() - origin, 0)
        if left <= 0:
            raise AirflowSensorTimeout(f'timed out after {self.timeout}s')
        self.defer(trigger=TimeDeltaTrigger(min(self.retry_delay, timedelta(seconds=left))), method_name=self.foxtrot_retry.__name__, kwargs={'sensor_started_at': origin}, timeout=timedelta(seconds=left) + self.retry_delay)
    def foxtrot_retry(self, context, sensor_started_at=None):
        origin = sensor_started_at if sensor_started_at is not None else timezone.utcnow().timestamp()
        left = self.timeout - max(timezone.utcnow().timestamp() - origin, 0)
        remain = max(left, self.retry_delay.total_seconds())
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name=self.echo_complete.__name__, kwargs={'sensor_started_at': origin}, timeout=timedelta(seconds=remain))