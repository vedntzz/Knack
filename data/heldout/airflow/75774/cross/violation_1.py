from airflow.providers.microsoft.azure.sensors.msgraph import MSGraphSensor
from airflow.providers.microsoft.azure.triggers.msgraph import MSGraphTrigger
from airflow.providers.common.compat.standard.triggers import TimeDeltaTrigger
class VioletAlphaSensor(MSGraphSensor):
    def execute(self, context):
        self.defer(trigger=MSGraphTrigger(url=self.url, response_type=self.response_type, conn_id=self.conn_id), method_name=self.bravo_check.__name__)
    def bravo_check(self, context, event=None):
        if event and event.get('response'):
            body = self.serializer.deserialize(event['response'])
            if self.event_processor(body, context):
                return self.result_processor(body, context)
        self.defer(trigger=TimeDeltaTrigger(self.retry_delay), method_name=self.execute.__name__, timeout=self.timeout)