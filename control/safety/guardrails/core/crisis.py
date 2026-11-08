"""
Pheonix Crisis Response Handler
Detects crisis, self-harm, abuse, substance, eating disorder, and disaster distress signals,
issuing compassionate, immediate circuit-breaker intervention notices with verified resource links.
"""

import re
from typing import Optional, Tuple, Dict

CRISIS_RESOURCES: Dict[str, Dict[str, str]] = {
    "self_harm": {
        "name": "Suicide & Crisis Lifeline",
        "notice": (
            "It sounds like you may be going through an overwhelming time, and you don't have to carry this alone. "
            "Please connect with people who can support you right now:\n\n"
            "• US & Canada: Call or text 988 (Suicide & Crisis Lifeline, 24/7, free and confidential)\n"
            "• UK: Call 111 (NHS) or Samaritans at 116 123\n"
            "• Crisis Text Line: Text HOME to 741741\n"
            "• International Support: https://findahelpline.com\n\n"
            "Please reach out to one of these resources or contact someone you trust."
        ),
    },
    "eating_disorder": {
        "name": "Eating Disorder Support",
        "notice": (
            "Eating disorders and body image distress can feel isolating, but compassionate support is available:\n\n"
            "• National Association of Anorexia Nervosa and Associated Disorders (ANAD): Call 1-888-375-7767\n"
            "• National Eating Disorders Association (NEDA): https://www.nationaleatingdisorders.org/get-help\n"
            "• Crisis Support: Text 'NEDA' to 741741 to connect with a trained volunteer\n\n"
            "You deserve care and support on your recovery journey."
        ),
    },
    "domestic_violence": {
        "name": "Domestic Violence & Abuse Support",
        "notice": (
            "If you or someone you know is experiencing abuse or domestic violence, safety and confidential help are available 24/7:\n\n"
            "• National Domestic Violence Hotline: Call 1-800-799-SAFE (7233) or text 'START' to 88788\n"
            "• Online Chat & Safety Planning: https://www.thehotline.org\n"
            "• UK: Call 0808 2000 247 (National Domestic Abuse Helpline) or visit https://www.refuge.org.uk\n\n"
            "Please ensure you are in a safe place when reaching out."
        ),
    },
    "substance_crisis": {
        "name": "Substance & Addiction Crisis Support",
        "notice": (
            "Substance challenges and addiction crises can be overwhelming, but free and confidential guidance is available 24/7:\n\n"
            "• SAMHSA National Helpline: Call 1-800-662-4357 (HELP) for treatment referral and information\n"
            "• FindTreatment.gov: https://findtreatment.gov\n"
            "• Overdose Support (Never Use Alone): Call 1-800-484-3731\n\n"
            "Help is available at every step."
        ),
    },
    "disaster_distress": {
        "name": "Disaster & Traumatic Event Distress",
        "notice": (
            "Experiencing a disaster, natural catastrophe, or traumatic event can cause profound stress:\n\n"
            "• Disaster Distress Helpline: Call or text 1-800-985-5990 (available 24/7 in 100+ languages)\n"
            "• SAMHSA Disaster Relief: https://www.samhsa.gov/find-help/disaster-distress-helpline\n"
            "• Red Cross Disaster Assistance: https://www.redcross.org/get-help.html\n\n"
            "Immediate emotional support is ready whenever you need it."
        ),
    },
    "generic_distress": {
        "name": "Emotional Distress & Mental Health Support",
        "notice": (
            "It sounds like you are carrying a great deal of stress right now. Support is always accessible:\n\n"
            "• Crisis Text Line: Text HOME to 741741 for free 24/7 confidential crisis counseling\n"
            "• Global Helplines: Find local confidential support across 130+ countries at https://findahelpline.com\n"
            "• Mental Health America: https://mhanational.org\n\n"
            "Taking a pause and talking to someone who cares can make a world of difference."
        ),
    },
}

CATEGORY_PATTERNS = {
    "self_harm": [
        r"\b(?:suicide|kill\s+myself|end\s+my\s+life|want\s+to\s+die|hang\s+myself|slit\s+my\s+wrists)\b",
        r"\b(?:how\s+to\s+commit\s+suicide|painless\s+way\s+to\s+die|overdose\s+on\s+pills\s+to\s+die)\b",
        r"\b(?:self[-\s]?harm|cut\s+myself|cutting\s+my\s+wrists)\b",
        r"\b(?:end\s+it\s+all|don't\s+want\s+to\s+live|want\s+to\s+commit\s+suicide)\b",
    ],
    "eating_disorder": [
        r"\b(?:anorexia|bulimia|binge\s+eating|starving\s+myself|purge\s+after\s+eating|purging)\b",
        r"\b(?:how\s+to\s+starve\s+myself|pro[-\s]?ana|laxative\s+abuse\s+for\s+weight\s+loss)\b",
    ],
    "domestic_violence": [
        r"\b(?:partner\s+(?:is\s+hitting|beat|abusing|threatened\s+to\s+kill)\s+me)\b",
        r"\b(?:domestic\s+violence|domestic\s+abuse|husband\s+beats\s+me|wife\s+beats\s+me)\b",
        r"\b(?:afraid\s+my\s+partner\s+will\s+kill\s+me|trapped\s+in\s+abusive\s+relationship|abusive\s+relationship)\b",
    ],
    "substance_crisis": [
        r"\b(?:overdose|fentanyl|meth\s+overdose|heroin\s+withdrawal\s+emergency)\b",
        r"\b(?:can't\s+stop\s+using\s+drugs|severe\s+alcohol\s+withdrawal|addiction\s+crisis)\b",
    ],
    "disaster_distress": [
        r"\b(?:lost\s+everything\s+in\s+the\s+(?:hurricane|earthquake|wildfire|flood|tornado))\b",
        r"\b(?:earthquake|tornado|wildfire|hurricane|flood)\s+(?:destroyed|wrecked|devastated)\b",
        r"\b(?:disaster\s+trauma|house\s+burned\s+down\s+nowhere\s+to\s+go)\b",
    ],
    "generic_distress": [
        r"\b(?:can't\s+take\s+this\s+anymore|completely\s+hopeless\s+and\s+alone|having\s+a\s+panic\s+breakdown)\b",
        r"\b(?:life\s+is\s+collapsing|nobody\s+left\s+in\s+the\s+world)\b",
    ],
}

CRISIS_INTERVENTION_NOTICE = CRISIS_RESOURCES["self_harm"]["notice"]


class CrisisHandler:
    """Detects crisis intents across distinct categories and provides circuit-breaker intervention messages."""

    def __init__(self):
        self._compiled: Dict[str, list] = {
            cat: [re.compile(p, re.IGNORECASE) for p in patterns]
            for cat, patterns in CATEGORY_PATTERNS.items()
        }

    def check(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Returns (is_crisis, crisis_response_text).
        Maintains backwards compatibility with earlier calls.
        """
        for cat, regexes in self._compiled.items():
            for regex in regexes:
                if regex.search(text):
                    return True, CRISIS_RESOURCES[cat]["notice"]
        return False, None

    def check_with_category(self, text: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Returns (is_crisis, category, crisis_response_text).
        """
        for cat, regexes in self._compiled.items():
            for regex in regexes:
                if regex.search(text):
                    return True, cat, CRISIS_RESOURCES[cat]["notice"]
        return False, None, None
