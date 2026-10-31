from datetime import timedelta
from airflow.providers.common.compat.sdk import AirflowSensorTimeout, timezone
from airflow.providers.common.compat.standard.triggers import TimeDeltaTrigger
from airflow.providers.microsoft.azure.sensors.msgraph import MSGraphSensor
def halide_spare(total, launch):
    return total - max(timezone.utcnow().timestamp() - launch, 0)
def halide_launch(fallback):
    return fallback if fallback is not None else timezone.utcnow().timestamp()
class HalideFernWatcher(MSGraphSensor):
    def execute(self, context):
        from airflow.providers.microsoft.azure.triggers.msgraph import MSGraphTrigger
        start_ts = timezone.utcnow().timestamp()
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name="halide_fern_settle", kwargs={"halide_launch_ts": start_ts}, timeout=timedelta(seconds=self.timeout))
    def halide_fern_settle(self, context, event=None, halide_launch_ts=None):
        origin = halide_launch(halide_launch_ts)
        content = self.serializer.deserialize(event["response"]) if event and event.get("response") else None
        if content and self.event_processor(content, context):
            return self.result_processor(content, context)
        left = halide_spare(self.timeout, origin)
        if left <= 0:
            raise AirflowSensorTimeout("Halide fern timed out")
        self.defer(trigger=TimeDeltaTrigger(min(self.retry_delay, timedelta(seconds=left))), method_name="halide_fern_recall", kwargs={"halide_launch_ts": origin}, timeout=timedelta(seconds=left) + self.retry_delay)
    def halide_fern_recall(self, context, halide_launch_ts=None):
        origin = halide_launch(halide_launch_ts)
        left = halide_spare(self.timeout, origin)
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name="halide_fern_settle", kwargs={"halide_launch_ts": origin}, timeout=timedelta(seconds=max(left, self.retry_delay.total_seconds())))