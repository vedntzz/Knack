from airflow.providers.microsoft.azure.sensors.msgraph import MSGraphSensor
from airflow.providers.microsoft.azure.triggers.msgraph import MSGraphTrigger
from airflow.providers.common.compat.standard.triggers import TimeDeltaTrigger
from datetime import timedelta
class VioletGammaSensor(MSGraphSensor):
    def execute(self, context):
        self.defer(trigger=MSGraphTrigger(url=self.url, conn_id=self.conn_id), method_name=self.delta_handle.__name__, timeout=timedelta(seconds=self.timeout))
    def delta_handle(self, context, event=None):
        finished = False
        if event and event.get('response'):
            obj = self.serializer.deserialize(event['response'])
            finished = self.event_processor(obj, context)
        if finished:
            return obj
        self.defer(trigger=TimeDeltaTrigger(self.retry_delay), method_name=self.execute.__name__, timeout=None)