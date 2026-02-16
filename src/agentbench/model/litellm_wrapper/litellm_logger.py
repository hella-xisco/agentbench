# custom_callbacks.py
import json
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
import traceback

# Import the CustomLogger from litellm
from litellm.integrations.custom_logger import CustomLogger
import pickle as pkl

DEBUG = False

# Log path configuration
LOG_PATH = "logs/litellm_server/traces/"   
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

def _json_default(o):
    """
    Helper to handle non-serializable objects (datetime, Pydantic models, etc.)
    """
    if isinstance(o, timedelta):
        return o.total_seconds()
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, bytes):
        return o.decode("utf-8", "replace")
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, set):
        return list(o)
    
    # Handle Pydantic v2
    if hasattr(o, "model_dump"):
        return o.model_dump()
    # Handle Pydantic v1
    if hasattr(o, "dict"):
        return o.dict()
    
    # Handle NamedTuples
    if hasattr(o, "_asdict"):
        return o._asdict()

    # Handle Dataclasses
    try:
        import dataclasses
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
    except Exception:
        pass
    
    if hasattr(o, "__dict__"):
        return o.__dict__
    
    # Fallback
    return repr(o)

class FileLogger(CustomLogger):
    def __init__(self):
        super().__init__()
        self.log_path = LOG_PATH

    def _extract_request_data(self, kwargs):
        """
        Helper to robustly extract the input data regardless of model type.
        Prioritizes: messages (Chat) -> input (Embedding) -> prompt (Text)
        """
        return (
            kwargs.get("messages") 
            or kwargs.get("input") 
            or kwargs.get("prompt") 
            or []
        )

    def _extract_api_key(self, kwargs):
        """
        Helper to extract user_api_key from litellm_params.
        """
        litellm_params = kwargs.get("litellm_params", {})
        print("litellm_params:", litellm_params)

        api_key = None
        metadata = litellm_params.get("metadata", {})
        if metadata is not None:
            api_key = metadata.get("user_api_key", None)
        if api_key is None:
            litellm_metadata = litellm_params.get("litellm_metadata", {})
            if litellm_metadata is not None:
                api_key = litellm_metadata.get("user_api_key", None)

        if api_key is not None:
            return api_key

        return "no_key"


    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        
        if DEBUG:
            pkl_path = f"{self.log_path}/pkl_kwargs.pkl"
            response_obj_path = f"{self.log_path}/pkl_response_obj.pkl"
            with open(pkl_path, "ab") as pf:
                pkl.dump(kwargs, pf)
            with open(response_obj_path, "ab") as rf:
                pkl.dump(response_obj, rf)
        
        try:
            api_key = self._extract_api_key(kwargs)
            model_name = kwargs.get("model", "unknown_model")

            request_data = self._extract_request_data(kwargs)

            rec = {
                "ts": time.time(),
                "event": "success",
                "model": model_name,
                "request": request_data,
                "response": response_obj,
                "api_key": api_key,
            }
                
            file_path = f"{self.log_path}/{api_key}.json"


            try:
                json_dump = json.dumps(rec, default=_json_default)
            except Exception as e:
                simple_response = {
                    "choices": [{"message": {"role": choice.message.role, "content": choice.message.content}} for choice in response_obj.choices]
                }
                                    
                rec = {
                    "ts": time.time(),
                    "event": "success",
                    "model": model_name,
                    "request": request_data,
                    "response": simple_response,
                    "api_key": api_key,
                }
            
                json_dump  = json.dumps(rec, default=_json_default)
            
            # Use the robust serializer
            with open(file_path, "a", buffering=1) as f:
                f.write(json_dump + "\n")
                
            
        except Exception as e:
            # Dumb the error to a file
            if DEBUG:
                error_path = f"{self.log_path}/logger_errors.txt"
                with open(error_path, "a") as ef:
                    ef.write(f"Error logging success event: {str(e)}\n")
                    ef.write(traceback.format_exc() + "\n")

            # Print error to stderr so you know if the logger itself is failing
            print(f"FileLogger Error (Success Event): {e}")

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):

        if DEBUG:
            pkl_path = f"{self.log_path}/pkl_kwargs_fail.pkl"
            with open(pkl_path, "ab") as pf:
                pkl.dump(kwargs, pf)

        try:
            api_key = self._extract_api_key(kwargs)
            model_name = kwargs.get("model", "unknown_model")

            request_data = self._extract_request_data(kwargs)
            
            rec = {
                "ts": time.time(),
                "event": "failure",
                "model": model_name,
                "request": request_data,
                "litellm_call_id": kwargs.get("litellm_call_id", ""),
                "response": response_obj,
                "exception": str(kwargs.get("exception", "")), 
                "api_key": api_key,
            }

            file_path = f"{self.log_path}/{api_key}.json"
            
            # Use the robust serializer
            with open(file_path, "a", buffering=1) as f:
                f.write(json.dumps(rec, default=_json_default) + "\n")
                
        except Exception as e:
            print(f"FileLogger Error (Failure Event): {e}")

# Instance to be used in config
file_logger = FileLogger()