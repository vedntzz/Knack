from airflow.providers.microsoft.azure.sensors.msgraph import MSGraphSensor
from airflow.providers.microsoft.azure.triggers.msgraph import MSGraphTrigger
from airflow.providers.common.compat.standard.triggers import TimeDeltaTrigger
from airflow.providers.common.compat.sdk import AirflowSensorTimeout, timezone
from datetime import timedelta
class AmberGoodThree(MSGraphSensor):
    def execute(self, context):
        ts = timezone.utcnow().timestamp()
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name=self.juliet_done.__name__, kwargs={'sensor_started_at': ts}, timeout=timedelta(seconds=self.timeout))
    def juliet_done(self, context, event=None, sensor_started_at=None):
        done = False
        for evt in [event]:
            if evt and evt.get('response'):
                body = self.serializer.deserialize(evt['response'])
                done = self.event_processor(body, context)
                if done:
                    return self.result_processor(body, context)
        base = sensor_started_at
        if base is None:
            base = timezone.utcnow().timestamp()
        remaining = self.timeout - max(timezone.utcnow().timestamp() - base, 0)
        if remaining <= 0:
            raise AirflowSensorTimeout(f'exceeded {self.timeout}')
        self.defer(trigger=TimeDeltaTrigger(min(self.retry_delay, timedelta(seconds=remaining))), method_name=self.kilo_retry.__name__, kwargs={'sensor_started_at': base}, timeout=timedelta(seconds=remaining) + self.retry_delay)
    def kilo_retry(self, context, sensor_started_at=None):
        base = sensor_started_at if sensor_started_at is not None else timezone.utcnow().timestamp()
        rem = self.timeout - max(timezone.utcnow().timestamp() - base, 0)
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name=self.juliet_done.__name__, kwargs={'sensor_started_at': base}, timeout=timedelta(seconds=max(rem, self.retry_delay.total_seconds())))