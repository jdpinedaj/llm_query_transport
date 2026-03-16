"""
Centralized Prompt Loader.
--------------------------
LLM Query Transport - Dynamic Prompt Template Management System

Loads prompt templates from YAML configuration files,
supporting both simple and few-shot prompting with FAISS.
"""

import logging
import warnings
from pathlib import Path
from typing import Any

import yaml
from langchain_community.vectorstores import FAISS
from langchain_core.example_selectors import SemanticSimilarityExampleSelector
from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate

from src.config.settings import logger

# Suppress FAISS GPU-related warnings
warnings.filterwarnings("ignore", message=".*GPU.*")
warnings.filterwarnings("ignore", category=UserWarning, message=".*faiss.*")
faiss_logger = logging.getLogger("faiss")
faiss_logger.setLevel(logging.ERROR)


class PromptLoader:
    """Centralized prompt loader that loads prompts from YAML files."""

    def __init__(self, prompts_dir: str = "src/config/prompts"):
        self.prompts_dir = Path(prompts_dir)
        self.prompts_cache: dict[str, dict[str, Any]] = {}
        self._load_all_prompts()

    def _load_all_prompts(self):
        """Load all YAML prompt files from the prompts directory."""
        for yaml_file in self.prompts_dir.glob("*.yml"):
            with open(yaml_file, encoding="utf-8") as f:
                prompts = yaml.safe_load(f)
                self.prompts_cache[yaml_file.stem] = prompts
                logger.debug(f"Loaded prompts from {yaml_file}")

    def get_prompt_template(self, file_name: str, prompt_name: str) -> PromptTemplate:
        """Get a LangChain PromptTemplate from YAML configuration."""
        try:
            prompt_config = self.prompts_cache[file_name][prompt_name]
            return PromptTemplate(
                input_variables=prompt_config["input_variables"],
                template=prompt_config["template"],
            )
        except KeyError as e:
            raise ValueError(f"Prompt '{prompt_name}' not found in '{file_name}.yml': {e}") from e

    def get_few_shot_template(
        self,
        file_name: str,
        prompt_name: str,
        examples: list[dict[str, str]],
        embeddings_model,
        k: int = 5,
    ) -> FewShotPromptTemplate:
        """Get a FewShot PromptTemplate from YAML configuration."""
        try:
            prompt_config = self.prompts_cache[file_name][prompt_name]

            example_selector = SemanticSimilarityExampleSelector.from_examples(
                examples=examples,
                embeddings=embeddings_model,
                vectorstore_cls=FAISS,
                k=k,
                input_keys=["input"],
            )

            example_prompt = PromptTemplate.from_template(prompt_config["example_template"])

            return FewShotPromptTemplate(
                example_selector=example_selector,
                example_prompt=example_prompt,
                prefix=prompt_config["prefix"],
                suffix=prompt_config["suffix"],
                input_variables=prompt_config["input_variables"],
            )
        except KeyError as e:
            raise ValueError(f"FewShot prompt '{prompt_name}' not found in '{file_name}.yml': {e}") from e

    def get_raw(self, file_name: str, key: str) -> Any:
        """Get a raw value from a YAML file."""
        return self.prompts_cache[file_name][key]

    def get_formatted_prompt(self, file_name: str, prompt_name: str, **kwargs: str) -> str:
        """Get a formatted prompt string from YAML configuration."""
        try:
            prompt_config = self.prompts_cache[file_name][prompt_name]
            template = prompt_config["template"]
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Prompt '{prompt_name}' not found in '{file_name}.yml': {e}") from e

    def get_nested_prompt(self, file_name: str, *path_components: str, **kwargs: str) -> str:
        """Get a nested prompt from YAML configuration and format it."""
        try:
            current = self.prompts_cache[file_name]
            for component in path_components:
                current = current[component]
            template = current["template"]
            return template.format(**kwargs)
        except KeyError as e:
            path = " -> ".join(path_components)
            raise ValueError(f"Nested prompt '{path}' not found in '{file_name}.yml': {e}") from e

    def reload_prompts(self):
        """Reload all prompts from YAML files."""
        self.prompts_cache.clear()
        self._load_all_prompts()
        logger.info("All prompts reloaded from YAML files")


prompt_loader = PromptLoader()
