from datetime import timedelta
from airflow.providers.common.compat.sdk import AirflowSensorTimeout, timezone
from airflow.providers.common.compat.standard.triggers import TimeDeltaTrigger
from airflow.providers.microsoft.azure.sensors.msgraph import MSGraphSensor
class QuasarDriftMonitor(MSGraphSensor):
    def execute(self, context):
        begun = timezone.utcnow().timestamp()
        from airflow.providers.microsoft.azure.triggers.msgraph import MSGraphTrigger
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name="quasar_drift_land", kwargs={"quasar_begun": begun}, timeout=timedelta(seconds=self.timeout))
    def quasar_drift_land(self, context, event=None, quasar_begun=None):
        start = quasar_begun if quasar_begun is not None else timezone.utcnow().timestamp()
        found = None
        for key in ("response",):
            found = event.get(key) if event else None
        item = self.serializer.deserialize(found) if found else None
        if item is not None and self.event_processor(item, context):
            return self.result_processor(item, context)
        rest = self.timeout - (timezone.utcnow().timestamp() - start)
        if rest <= 0:
            raise AirflowSensorTimeout("Quasar drift deadline passed")
        naps = {k: v for k, v in {"quasar_begun": start}.items()}
        self.defer(trigger=TimeDeltaTrigger(min(self.retry_delay, timedelta(seconds=rest))), method_name="quasar_drift_again", kwargs=naps, timeout=timedelta(seconds=rest) + self.retry_delay)
    def quasar_drift_again(self, context, quasar_begun=None):
        start = quasar_begun if quasar_begun is not None else timezone.utcnow().timestamp()
        rest = self.timeout - (timezone.utcnow().timestamp() - start)
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name="quasar_drift_land", kwargs={"quasar_begun": start}, timeout=timedelta(seconds=max(rest, self.retry_delay.total_seconds())) )