# common_imports.py

import os
import json
import sys
import time
import pathlib
import requests

from openai import AzureOpenAI
from azure.core.exceptions import AzureError
from IPython.display import display, Markdown
from datetime import datetime
from azure.core.exceptions import HttpResponseError
import pandas as pd

