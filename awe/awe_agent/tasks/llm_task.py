from ...celery import app
from typing import Optional, List
from transformers import MistralForCausalLM, LlamaTokenizerFast, AutoModelForCausalLM, AutoTokenizer
import torch
from ...models.awe_agent import LLMConfig

class LLMRunner:
    model: MistralForCausalLM
    tokenizer: LlamaTokenizerFast
    model_name: str = ""

    def load_model(self, llm_config: LLMConfig):
       if llm_config.model_name != self.model_name:
          self.model_name = llm_config.model_name
          args = {
              "torch_dtype": torch.bfloat16,
              "cache_dir": "models/huggingface"
          }
          if llm_config.hf_token != "" and llm_config.hf_token is not None:
             args["token"] = llm_config.hf_token

          self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name, **args).to("cuda")

          self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, **args)

    def invoke(self, llm_config: LLMConfig, prompt: str, stop: Optional[List[str]] = None) -> str:

        self.load_model(llm_config)

        messages = [
         {"role": "user", "content": prompt},
        ]

        encodeds = self.tokenizer.apply_chat_template(messages, return_tensors="pt")
        model_inputs = encodeds.to(self.model.device)

        generated_ids = self.model.generate(
           model_inputs,
           max_new_tokens=512,
           do_sample=True,
           pad_token_id=self.tokenizer.eos_token_id,
           top_k=4,
           temperature=0.7
        )

        decoded = self.tokenizer.batch_decode(generated_ids)

        output = decoded[0].split("[/INST]")[1].replace("</s>", "").strip()

        if stop is not None:
          for word in stop:
            output = output.split(word)[0].strip()

        while not output.endswith("```"):
          output += "`"

        return output


runner: LLMRunner = None

def get_runner() -> LLMRunner:
    global runner
    if runner is None:
      runner = LLMRunner()
    return runner

@app.task
def llm(llm_config, prompt: str, stop: Optional[List[str]] = None):
    return get_runner().invoke(LLMConfig.model_validate(llm_config), prompt, stop)
