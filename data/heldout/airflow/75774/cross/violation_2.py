from airflow.providers.microsoft.azure.sensors.msgraph import MSGraphSensor
from airflow.providers.microsoft.azure.triggers.msgraph import MSGraphTrigger
from airflow.providers.common.compat.standard.triggers import TimeDeltaTrigger
def zulu_build(url, rt, cid):
    return MSGraphTrigger(url=url, response_type=rt, conn_id=cid)
class VioletBetaSensor(MSGraphSensor):
    def execute(self, context):
        self.defer(trigger=zulu_build(self.url, self.response_type, self.conn_id), method_name=self.charlie_process.__name__)
    def charlie_process(self, context, event=None):
        ok = False
        if event and event.get('response'):
            payload = self.serializer.deserialize(event['response'])
            ok = self.event_processor(payload, context)
        if ok:
            return payload
        self.defer(trigger=TimeDeltaTrigger(self.retry_delay), method_name=self.execute.__name__, timeout=self.timeout)