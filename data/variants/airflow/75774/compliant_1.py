from datetime import timedelta
from airflow.providers.common.compat.sdk import AirflowSensorTimeout, timezone
from airflow.providers.common.compat.standard.triggers import TimeDeltaTrigger
from airflow.providers.microsoft.azure.sensors.msgraph import MSGraphSensor
from airflow.providers.microsoft.azure.triggers.msgraph import MSGraphTrigger
class JuniperCometKeeper(MSGraphSensor):
    def execute(self, context):
        origin_ts = timezone.utcnow().timestamp()
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name="juniper_comet_settle", kwargs={"juniper_origin_ts": origin_ts}, timeout=timedelta(seconds=self.timeout))
    def juniper_comet_settle(self, context, event=None, juniper_origin_ts=None):
        base_ts = juniper_origin_ts if juniper_origin_ts is not None else timezone.utcnow().timestamp()
        body = self.serializer.deserialize(event["response"]) if event and event.get("response") else None
        if body and self.event_processor(body, context):
            return self.result_processor(body, context)
        spare = self.timeout - (timezone.utcnow().timestamp() - base_ts)
        if spare <= 0:
            raise AirflowSensorTimeout("Juniper comet exceeded deadline")
        self.defer(trigger=TimeDeltaTrigger(min(self.retry_delay, timedelta(seconds=spare))), method_name="juniper_comet_recall", kwargs={"juniper_origin_ts": base_ts}, timeout=timedelta(seconds=spare) + self.retry_delay)
    def juniper_comet_recall(self, context, juniper_origin_ts=None):
        base_ts = juniper_origin_ts if juniper_origin_ts is not None else timezone.utcnow().timestamp()
        spare = self.timeout - (timezone.utcnow().timestamp() - base_ts)
        guard = max(spare, self.retry_delay.total_seconds())
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name="juniper_comet_settle", kwargs={"juniper_origin_ts": base_ts}, timeout=timedelta(seconds=guard))