"""Run the knack CLI, logging every live Spark / Spark Open call's model, host and trace id. Driver only."""
import json, os, sys, time
from knack.pipeline.spark import SparkApi
from knack.pipeline.spark_open import SparkOpenApi
from knack.cli import main

LOG = os.environ["KNACK_SPIKE_MODELS"]
STEP = os.environ.get("KNACK_SPIKE_STEP", "")


def traced(cls):
    ask = cls.ask
    def wrapper(self, prompt):
        started = time.perf_counter()
        try:
            return ask(self, prompt)
        finally:
            row = {"step": STEP, "client": cls.__name__, "model": self.last_model, "host": self.host,
                   "trace_id": self.last_trace_id, "wall_s": round(time.perf_counter() - started, 1),
                   "prompt_head": prompt[:120]}
            with open(LOG, "a") as handle:
                handle.write(json.dumps(row) + "\n")
    cls.ask = wrapper


traced(SparkApi)
traced(SparkOpenApi)
sys.exit(main(sys.argv[1:]))
