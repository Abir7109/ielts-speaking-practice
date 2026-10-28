"""Question banks for IELTS Speaking Parts 1, 2 and 3."""
import random

PART1_TOPICS = [
    "hometown", "work/study", "family", "hobbies", "food",
    "travel", "technology", "sports", "music", "weather",
    "shopping", "reading", "friends", "daily routine", "future plans",
    "accommodation", "transport", "art", "cinema", "health",
]

PART1_QUESTIONS = {
    "hometown": [
        "Where are you from originally?",
        "What do you like most about your hometown?",
        "Has your hometown changed much in recent years?",
    ],
    "work/study": [
        "Do you work or are you a student?",
        "What do you enjoy most about your work or studies?",
        "Would you like to change your job or field of study in the future?",
    ],
    "family": [
        "Tell me about your family.",
        "Who are you closest to in your family?",
        "Do you spend a lot of time with your family at weekends?",
    ],
    "hobbies": [
        "What do you do in your free time?",
        "Did you have the same hobbies when you were a child?",
        "Do you think hobbies are important for a balanced life?",
    ],
    "food": [
        "What kind of food do you enjoy eating?",
        "Do you prefer eating at home or in restaurants?",
        "Has your diet changed much since you were a child?",
    ],
    "travel": [
        "Do you like travelling? Why or why not?",
        "What was the last trip you took?",
        "Where would you most like to visit in the future?",
    ],
    "technology": [
        "How important is technology in your daily life?",
        "What kind of technology do you use most often?",
        "Do you think young people use technology too much?",
    ],
    "sports": [
        "Do you play any sports or do any exercise regularly?",
        "What sports are popular where you come from?",
        "Do you prefer watching sport or taking part in it?",
    ],
    "music": [
        "What kind of music do you usually listen to?",
        "Has your taste in music changed over the years?",
        "Do you prefer live music or recorded music?",
    ],
    "weather": [
        "What is the weather usually like where you live?",
        "Do you prefer hot or cold weather?",
        "Does the weather affect your mood?",
    ],
    "shopping": [
        "Do you enjoy shopping? Why or why not?",
        "Do you prefer shopping in physical stores or online?",
        "How often do you buy clothes?",
    ],
    "reading": [
        "Do you enjoy reading? What do you usually read?",
        "Did you read more as a child than you do now?",
        "Is reading still important in the digital age?",
    ],
    "friends": [
        "Do you have many friends or just a few close ones?",
        "How often do you see your friends?",
        "What qualities do you value most in a friend?",
    ],
    "daily routine": [
        "Describe your typical day from morning to night.",
        "Has your daily routine changed in the last few years?",
        "What part of your routine do you enjoy most?",
    ],
    "future plans": [
        "What are your plans for the next few years?",
        "Do you prefer planning ahead or being spontaneous?",
        "Has your dream job changed since you were a child?",
    ],
    "accommodation": [
        "Do you live in a house or a flat?",
        "What do you like most about your home?",
        "Would you like to live somewhere else in the future?",
    ],
    "transport": [
        "How do you usually get around your city?",
        "Do you prefer public transport or driving?",
        "Has transport in your area improved in recent years?",
    ],
    "art": [
        "Do you enjoy visiting art galleries or museums?",
        "Do you think art is important in education?",
        "Is there a piece of art you remember well?",
    ],
    "cinema": [
        "How often do you go to the cinema?",
        "Do you prefer watching films at home or at the cinema?",
        "What kind of films do you enjoy most?",
    ],
    "health": [
        "Do you consider yourself a healthy person?",
        "What do you do to stay healthy?",
        "Do you think people today are healthier than in the past?",
    ],
}

PART2_CUE_CARDS = [
    {
        "topic": "Describe a person who has influenced you",
        "points": [
            "Who this person is",
            "How you know them",
            "What qualities they have",
            "Explain how they have influenced you",
        ],
        "follow_up_part3": [
            "What qualities make a good role model?",
            "Do you think celebrities are good role models for young people?",
            "How has the concept of role models changed over the years?",
        ],
    },
    {
        "topic": "Describe a time you achieved something you were proud of",
        "points": [
            "What you achieved",
            "When you achieved it",
            "How you achieved it",
            "Explain why you were proud of it",
        ],
        "follow_up_part3": [
            "What kinds of achievements are most valued in your country?",
            "Is it important for children to learn to deal with failure?",
            "Do you think people today put too much pressure on themselves to succeed?",
        ],
    },
    {
        "topic": "Describe a place you would like to visit",
        "points": [
            "Where it is",
            "What it looks like",
            "Why you want to visit",
            "Explain what you would do there",
        ],
        "follow_up_part3": [
            "Why do people like to travel to other countries?",
            "What are the advantages and disadvantages of tourism?",
            "How has international travel changed in recent decades?",
        ],
    },
    {
        "topic": "Describe a book or film that made an impression on you",
        "points": [
            "What the book or film was",
            "When you read or watched it",
            "What it was about",
            "Explain why it made an impression on you",
        ],
        "follow_up_part3": [
            "How important is it to encourage children to read?",
            "Do you think films can teach us important life lessons?",
            "How has the film industry changed with streaming services?",
        ],
    },
    {
        "topic": "Describe a skill you have learned that is useful",
        "points": [
            "What the skill is",
            "How you learned it",
            "How long it took",
            "Explain why it is useful",
        ],
        "follow_up_part3": [
            "What skills do you think are most important in today's world?",
            "Should practical skills be taught more in schools?",
            "How has technology changed the skills people need?",
        ],
    },
    {
        "topic": "Describe an interesting conversation you had",
        "points": [
            "Who you had it with",
            "Where you were",
            "What you talked about",
            "Explain why you found it interesting",
        ],
        "follow_up_part3": [
            "How important is communication in the workplace?",
            "Do you think people communicate differently online than face to face?",
            "How can misunderstandings in communication be avoided?",
        ],
    },
    {
        "topic": "Describe a piece of technology you use often",
        "points": [
            "What it is",
            "How you use it",
            "How often you use it",
            "Explain why it is important to you",
        ],
        "follow_up_part3": [
            "How has technology changed the way we work?",
            "Are there any negative effects of people using technology too much?",
            "How do you think technology will develop in the next 20 years?",
        ],
    },
    {
        "topic": "Describe a memorable journey",
        "points": [
            "Where you went",
            "Who you went with",
            "What happened on the journey",
            "Explain why you remember it well",
        ],
        "follow_up_part3": [
            "How has the way people travel changed in the last 50 years?",
            "Is domestic or international travel more interesting?",
            "Will people travel less in the future because of technology?",
        ],
    },
    {
        "topic": "Describe a teacher who influenced you",
        "points": [
            "Who the teacher was",
            "What subject they taught",
            "What made them special",
            "Explain how they influenced you",
        ],
        "follow_up_part3": [
            "What makes a good teacher?",
            "How has teaching changed with technology?",
            "Should teachers be paid more than other professionals?",
        ],
    },
    {
        "topic": "Describe a decision you regret",
        "points": [
            "What the decision was",
            "When you made it",
            "Why you made it",
            "Explain why you regret it",
        ],
        "follow_up_part3": [
            "Do people learn more from mistakes than from successes?",
            "Should young people take more risks?",
            "How can people make better decisions?",
        ],
    },
    {
        "topic": "Describe a busy public place you often go to",
        "points": [
            "Where it is",
            "How often you go there",
            "What you do there",
            "Explain why you like going there",
        ],
        "follow_up_part3": [
            "Why do people enjoy crowded places?",
            "Will city centres become less popular?",
            "How can cities make public spaces better?",
        ],
    },
    {
        "topic": "Describe something you do to stay healthy",
        "points": [
            "What you do",
            "How often you do it",
            "Who you do it with",
            "Explain how it keeps you healthy",
        ],
        "follow_up_part3": [
            "Why do some people find it hard to stay healthy?",
            "Should governments do more to promote healthy lifestyles?",
            "How has the definition of a healthy life changed?",
        ],
    },
    {
        "topic": "Describe a law in your country",
        "points": [
            "What the law is",
            "When it was introduced",
            "Whether people obey it",
            "Explain whether you think it is a good law",
        ],
        "follow_up_part3": [
            "Why do people break laws?",
            "Should laws be the same in every country?",
            "How can governments make people respect the law?",
        ],
    },
    {
        "topic": "Describe a celebration you attended",
        "points": [
            "What the celebration was",
            "When it happened",
            "Who was there",
            "Explain why it was memorable",
        ],
        "follow_up_part3": [
            "Why are celebrations important in every culture?",
            "Do modern celebrations have the same meaning as in the past?",
            "How do festivals bring communities together?",
        ],
    },
    {
        "topic": "Describe a goal you want to achieve in the future",
        "points": [
            "What the goal is",
            "Why it is important to you",
            "What you need to do to achieve it",
            "Explain how you will feel when you achieve it",
        ],
        "follow_up_part3": [
            "Is it better to set small goals or one big goal?",
            "Do people in your country usually achieve their goals?",
            "How has goal-setting changed with social media?",
        ],
    },
]

PART3_GENERIC_QUESTIONS = [
    "Why do you think people find it difficult to talk about this topic?",
    "How has this changed compared with twenty years ago?",
    "Do you think this will be more or less important in the future?",
    "Should the government or schools do more about this?",
    "How do different generations view this differently?",
    "What role does technology play in this?",
]


def get_part1_questions(topic: str = None) -> dict:
    if not topic:
        topic = random.choice(PART1_TOPICS)
    topic = topic.lower().strip()
    questions = PART1_QUESTIONS.get(topic)
    if not questions:
        # match loose keywords
        for key in PART1_QUESTIONS:
            if key.split("/")[0] in topic or topic in key:
                questions = PART1_QUESTIONS[key]
                topic = key
                break
    if not questions:
        questions = [
            f"How important is {topic} to you?",
            f"How often do you think about {topic}?",
            f"Has your attitude to {topic} changed as you have got older?",
        ]
    return {
        "part": 1,
        "topic": topic,
        "questions": questions,
        "time_limit_seconds": 240,
        "instructions": (
            "Answer naturally as in a real interview. Aim for 2-3 sentences "
            "per answer — not too short, not over-explained. Use varied vocabulary."
        ),
    }


def get_part2_cue_card() -> dict:
    card = random.choice(PART2_CUE_CARDS)
    return {
        "part": 2,
        "topic": card["topic"],
        "bullet_points": card["points"],
        "prep_time_seconds": 60,
        "speak_time_seconds": 120,
        "follow_up_part3": card["follow_up_part3"],
        "instructions": (
            "You have 1 minute to prepare. Then speak for 1-2 minutes. "
            "Cover all bullet points. Use the preparation time to make brief notes."
        ),
    }


def get_part3_questions(cue_card: dict = None) -> dict:
    if cue_card and cue_card.get("follow_up_part3"):
        questions = cue_card["follow_up_part3"]
    else:
        questions = random.sample(PART3_GENERIC_QUESTIONS, 4)
    return {
        "part": 3,
        "questions": questions,
        "time_limit_seconds": 300,
        "instructions": (
            "Give detailed, analytical answers. Show abstract thinking. "
            "Use discourse markers and sophisticated vocabulary."
        ),
    }
