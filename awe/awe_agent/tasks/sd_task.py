from ..celery import app
from sd_task.task_runner import run_inference_task
from sd_task.task_args import InferenceTaskArgs
from sd_task.config import Config
from sd_task.cache import MemoryModelCache
import base64
from io import BytesIO


class SDRunner:
    model_cache: MemoryModelCache = None

    def __init__(self):
        self.model_cache = MemoryModelCache()

    def invoke(self, task_args: InferenceTaskArgs) -> str:

        images = run_inference_task(
            task_args,
            config=Config.model_validate({
                "deterministic": False,
                "data_dir": {
                    "models": {
                        "huggingface": "models/huggingface",
                        "external": "models/external"
                    }
                }
            }),
            model_cache=self.model_cache
        )
        image = images[0]
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")


runner: SDRunner = None

def get_runner() -> SDRunner:
    global runner
    if runner is None:
        runner = SDRunner()
    return runner

@app.task
def sd(task_args):
    return get_runner().invoke(InferenceTaskArgs.model_validate(task_args))
