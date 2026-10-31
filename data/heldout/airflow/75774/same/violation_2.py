from datetime import timedelta
from airflow.providers.common.compat.standard.triggers import TimeDeltaTrigger
from airflow.providers.microsoft.azure.sensors.msgraph import MSGraphSensor
class CopperMeadowSentinel(MSGraphSensor):
    def _nap_args(self):
        return {"timeout": timedelta(seconds=self.timeout)}
    def execute_complete(self, context, event=None):
        for parcel in [event]:
            if not parcel:
                return None
            if parcel.get("response") and not self.event_processor(parcel["response"], context):
                opts = self._nap_args()
                self.defer(trigger=TimeDeltaTrigger(self.retry_delay), method_name=self.retry_execute.__name__, timeout=opts["timeout"])
        return None