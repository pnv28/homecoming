import math
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from estate_ranking.step_5 import scoring_policy

Category = Literal['Urban', 'Extended Urban', 'New Territories', 'Islands']


class Parameters(BaseModel):
    model_config = ConfigDict(extra='forbid')
    applicant_name: str = Field(default='', max_length=160)
    household_size: Optional[int] = Field(default=None, ge=1, le=30)
    housing_district: Optional[Category] = None
    wheelchair: bool = False
    hospital_id: Optional[str] = Field(default=None, max_length=120)
    scenario: Literal['primary', 'baseline'] = 'primary'
    weights: Dict[str, float] = Field(default_factory=lambda: dict(bus=1,mtr=1,hospital=1))

    @field_validator('weights', mode='before')
    @classmethod
    def valid_weights(cls, value):
        scoring_policy(value)
        return value


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirmed: Literal[True]
    parameters: Parameters


class Member(BaseModel):
    name: Optional[str] = Field(default=None,max_length=160)
    disability_codes: List[int] = Field(default_factory=list,max_length=6)

    @field_validator('disability_codes')
    @classmethod
    def valid_codes(cls, codes):
        if any(code not in range(1,7) for code in codes):
            raise ValueError('Unknown disability code.')
        return codes


class Evidence(BaseModel):
    page: int = Field(ge=1, le=12)
    text: str = Field(max_length=600)


class ExtractedProfile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    applicant_name: Optional[str] = Field(default=None,max_length=160)
    household_size: Optional[int] = Field(default=None,ge=1,le=30)
    housing_district: Optional[Category] = None
    wheelchair_required: Optional[bool] = None
    household: List[Member] = Field(default_factory=list,max_length=30)
    hospital_mentioned: Optional[str] = Field(default=None,max_length=250)
    issues: List[str] = Field(default_factory=list,max_length=20)
    evidence: List[Evidence] = Field(default_factory=list,max_length=30)


class Endpoint(BaseModel):
    latitude: float = Field(ge=-90,le=90,allow_inf_nan=False)
    longitude: float = Field(ge=-180,le=180,allow_inf_nan=False)
    label: str = Field(default='',max_length=160)


class WalkRequest(BaseModel):
    start: Endpoint
    end: Endpoint
    wheelchair: bool = False


class OverviewItem(BaseModel):
    estate_id: str
    explanation: str = Field(min_length=1,max_length=900)


class Overview(BaseModel):
    summary: str = Field(min_length=1,max_length=1400)
    top_three: List[OverviewItem] = Field(max_length=3)
    note: str = Field(default='',max_length=600)
