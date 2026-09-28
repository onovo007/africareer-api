"""Typed CV content shared by generation and reviewed export."""
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from quality import DraftValidationError

class Part(BaseModel):
    model_config=ConfigDict(extra='forbid',str_max_length=4000)
class Experience(Part):
    title:str=''
    company:str=''
    location:str=''
    dates:str=''
    bullets:list[str]=Field(default_factory=list,max_length=30)
class Education(Part):
    degree:str=''
    institution:str=''
    dates:str=''
class Project(Part):
    title:str=''
    dates:str=''
    description:str=''
    bullets:list[str]=Field(default_factory=list,max_length=30)
class CV(Part):
    full_name:str=''
    credentials:str=''
    contact_line:str=''
    professional_summary:str=''
    selected_achievements:list[str]=Field(default_factory=list,max_length=30)
    core_competencies:list[str]=Field(default_factory=list,max_length=40)
    work_experience:list[Experience]=Field(default_factory=list,max_length=30)
    education:list[Education]=Field(default_factory=list,max_length=20)
    publications:list[str]=Field(default_factory=list,max_length=30)
    projects:list[Project|str]=Field(default_factory=list,max_length=30)
    certifications:list[str]=Field(default_factory=list,max_length=30)
    technical_skills:str=''
    languages:list[str]=Field(default_factory=list,max_length=30)
    education_first:bool=False

def checked_cv(value):
    try:
        result=CV.model_validate(value).model_dump()
    except ValidationError:
        raise DraftValidationError('The CV structure is invalid. Keep dates, titles and bullets in their labelled fields.') from None
    if not any(result[k] for k in ('professional_summary','work_experience','education','projects')):
        raise DraftValidationError('Add education, experience, projects or a summary before exporting.')
    return result
