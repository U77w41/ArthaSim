"""Category lists, in the order arrays index them, and the index constants."""
import numpy as np

AGE_BANDS = ["18-24", "25-34", "35-44", "45-59", "60+"]
AGE_EDGES = [18, 25, 35, 45, 60, 85]
SEX = ["F", "M"]
EDUCATION = ["none", "primary", "secondary", "graduate", "postgraduate"]
LIFE_STAGE = ["studying", "seeking", "salaried", "self_employed", "gig", "farm", "casual",
              "homemaker", "retired"]
SECTORS = ["agriculture", "manufacturing", "construction", "trade", "transport", "it_services",
           "finance", "public_admin", "education_health", "other_services"]
MERCHANT_CATEGORIES = ["grocery", "food", "fuel", "pharmacy", "apparel", "electronics", "transport",
                       "services", "other"]

F, M = 0, 1
STUDYING, SEEKING, SALARIED, SELF_EMPLOYED, GIG, FARM, CASUAL, HOMEMAKER, RETIRED = range(9)
EARNING = (SALARIED, SELF_EMPLOYED, GIG, FARM, CASUAL)
GROCERY = 0
OTHER_SERVICES = 9
WORK = (SELF_EMPLOYED, GIG, FARM, CASUAL)
NON_EARNING = (STUDYING, SEEKING, HOMEMAKER, RETIRED)
PUBLIC_ADMIN = 7

# Five-year age groups of the life-course targets (PLFS Table 15 columns from age 18).
AGE_GROUPS = ["18-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65+"]
AGE_GROUP_EDGES = [18, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65]
N_AGE_GROUPS = 11


def age_group(age):
    """Index into AGE_GROUPS for each age (ages below 18 count as 18-19)."""
    idx = np.searchsorted(np.asarray(AGE_GROUP_EDGES), np.asarray(age), side="right") - 1
    return np.clip(idx, 0, N_AGE_GROUPS - 1)
