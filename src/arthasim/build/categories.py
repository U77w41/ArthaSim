"""Category lists, in the order arrays index them, and the index constants."""
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
