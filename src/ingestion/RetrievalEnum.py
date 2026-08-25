"""
Enums used to classify scraped sources.

Fixes applied vs. the original RetrivalEnum.py:
- Fixed filename typo (Retrival -> Retrieval); old import path kept as a
  backward-compat shim (see RetrivalEnum.py) so existing imports don't break.
- Added GLOBAL_GOVERNANCE and NATIONAL_STRATEGY to SourceCategory, and
  DATA_PROTECTION - the original sources.yaml/design already needed these
  values but they didn't exist in the enum, so validation would have failed.
"""
from enum import Enum


class ScrapeStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class SourceType(str, Enum):
    OFFICIAL = "official"
    LEGAL = "legal"
    GOVERNMENT = "government"
    RESEARCH = "research"
    ACADEMIC = "academic"
    INDUSTRY = "industry"
    CIVIL_SOCIETY = "civil_society"
    INTERNATIONAL = "international"
    SOCIAL_OPINION = "social_opinion"
    OTHER = "other"


class SourceCategory(str, Enum):
    REGULATION = "regulation"
    PRIMARY_LEGISLATION = "primary_legislation"
    IMPLEMENTATION = "implementation"
    POLICY = "policy"
    AI_GOVERNANCE = "ai_governance"
    NATIONAL_STRATEGY = "national_strategy"       # added: Egypt's AI strategy is not "regulation" per se
    DATA_PROTECTION = "data_protection"            # added: Egypt's Law 151/2020 is data protection, not general "policy"
    GLOBAL_GOVERNANCE = "global_governance"         # added: was used in sources.yaml but never defined
    DIGITAL_RIGHTS = "digital_rights"
    HUMAN_RIGHTS = "human_rights"
    ALGORITHMIC_ACCOUNTABILITY = "algorithmic_accountability"
    ACADEMIC = "academic"
    TECHNOLOGY = "technology"
    PUBLIC_OPINION = "public_opinion"
    OTHER = "other"
