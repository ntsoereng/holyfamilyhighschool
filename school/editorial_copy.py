"""Reviewed learner-facing versions of recognised imported curriculum text.

Only exact source fields are replaced. Independently edited text stays untouched.
"""

CURRICULUM_COPY = {'old_body': '<p>Our Curriculum Overview</p><h2>A Commitment to Excellence</h2><p>Holy Family High School '
             'aims at offering all our students a broad and balanced curriculum that provides rewarding and '
             'stimulating activities to prepare them for the best social and cultural life.</p><p>Whether it '
             'is our books or hands-on training, we make sure each student gets personal attention to cope '
             'and flourish in every subject for better scores and a brighter future, while aligning with the '
             'Lesotho General Certificate of Secondary Education (LGCSE) Curriculum.</p>',
 'old_introduction': 'A broad education in languages, sciences, humanities and practical subjects.',
 'body': '<h2>Your learning at Holy Family</h2><p>Your curriculum brings together languages, sciences, '
         'humanities and practical subjects, aligned with the Lesotho General Certificate of Secondary '
         'Education (LGCSE).</p><p>Through classroom learning, reading and practical work, you can build '
         'your understanding, develop your skills and prepare for life beyond school. Explore the subjects '
         'below to see where your learning can take you.</p>',
 'introduction': 'Explore languages, sciences, humanities and practical subjects as you prepare for the '
                 'Lesotho General Certificate of Secondary Education (LGCSE).'}

SUBJECT_COPY = {'english': {'title': 'English',
             'old_body': '<p>English is a crucial subject for high school students as it lays the foundation '
                         'for effective communication, critical thinking, and analysis skills. In this '
                         'subject, students learn to read, write, speak, and listen effectively, enhancing '
                         'their ability to express themselves confidently and clearly. . Additionally, '
                         'English classes help students improve their vocabulary, grammar, and syntax, '
                         'enabling them to communicate effectively in both written and spoken forms. Mastery '
                         'of the English language is essential for success in any profession, and the '
                         'subject prepares students for college and career opportunities. Thus, English is a '
                         'vital subject as it provides students with the skills and tools necessary for '
                         'personal and professional growth.</p>',
             'old_introduction': 'English is a crucial subject for high school students as it lays the '
                                 'foundation for effective communication, critical thinking, and analysis '
                                 'skills. In this subject, students…',
             'body': '<p>In English, you develop your vocabulary, grammar and sentence structure while '
                     'practising how to read, write, speak and listen effectively. You learn to analyse '
                     'texts, think critically and explain your ideas with clarity.</p><p>These skills '
                     'support your learning across subjects and help you prepare for further study, work and '
                     'everyday communication.</p>',
             'introduction': 'Build your confidence in reading, writing, speaking and listening, and learn '
                             'to communicate your ideas clearly.'},
 'sesotho': {'title': 'Sesotho',
             'old_body': '<p>Sesotho is the native language in Lesotho that most of our learners have grown '
                         'up speaking from their early childhood. Native language refers to the language '
                         'that a person learns as their first language during childhood and continues to use '
                         'as their primary means of communication. In this curriculum, the study of our '
                         'native language involves developing proficiency in reading, writing, speaking, and '
                         'listening in the language. The course covers topics such as grammar, vocabulary, '
                         'literature, and communication skills. Through studying their native language, '
                         'students develop a deeper understanding and appreciation of their culture and '
                         'heritage, as well as the ability to communicate effectively with others in the '
                         'language. Additionally, the study of Sesotho provides a foundation for learning '
                         'other languages and for developing cross-cultural communication skills. Native '
                         'language is relevant to many aspects of daily life, including personal '
                         'communication, education, and career opportunities.</p>',
             'old_introduction': 'Sesotho is the native language in Lesotho that most of our learners have '
                                 'grown up speaking from their early childhood. Native language refers to '
                                 'the language…',
             'body': '<p>Your study of Sesotho brings together grammar, vocabulary, literature and '
                     'communication. You practise reading, writing, speaking and listening so you can '
                     'express yourself clearly and understand others.</p><p>As you explore the language and '
                     'its literature, you deepen your understanding of culture and heritage and build skills '
                     'that support communication in school and daily life.</p>',
             'introduction': 'Strengthen your Sesotho reading, writing, speaking and listening while '
                             'exploring language, literature and cultural heritage.'},
 'mathematics': {'title': 'Mathematics',
                 'old_body': '<p>Mathematics is a fundamental subject that is essential for high school '
                             'students to learn. It involves the study of numbers, shapes, patterns, and '
                             'relationships between them, and it teaches students how to use logic and '
                             'reasoning to solve problems. Math is a crucial subject because it is used in '
                             'many real-life situations, from calculating taxes to analyzing data, designing '
                             'buildings, and making financial decisions. The study of mathematics helps '
                             'students develop critical thinking skills, as they learn how to analyze '
                             'problems, identify patterns, and develop logical arguments. The subject also '
                             'teaches students how to communicate their reasoning effectively and clearly, '
                             "both in writing and verbally. This skill is particularly important in today's "
                             'world, where data analysis and mathematical modeling are increasingly used in '
                             'many fields, including science, engineering, finance, and economics.</p>',
                 'old_introduction': 'Mathematics is a fundamental subject that is essential for high school '
                                     'students to learn. It involves the study of numbers, shapes, patterns, '
                                     'and relationships between them,…',
                 'body': '<p>In Mathematics, you investigate numbers, shapes, patterns and the relationships '
                         'between them. You learn to identify problems, choose an approach, work through '
                         'calculations and explain your reasoning clearly.</p><p>You also explore how '
                         'mathematics connects to everyday decisions and to fields such as science, '
                         'engineering and finance, including the use of data and mathematical models.</p>',
                 'introduction': 'Explore numbers, shapes, patterns and relationships, and use logical '
                                 'reasoning to solve problems and explain your thinking.'},
 'chemistry': {'title': 'Chemistry',
               'old_body': '<p>Chemistry is the branch of science that deals with the composition, '
                           'structure, and properties of matter, as well as the changes it undergoes during '
                           'chemical reactions. In this curriculum, chemistry is a foundational science '
                           'course that focuses on introducing students to the fundamental concepts and '
                           'principles of chemistry, such as atomic structure, chemical bonding, reactions, '
                           'and the periodic table. Through hands-on laboratory experiments and classroom '
                           'lectures, students will develop critical thinking and problem-solving skills, as '
                           'well as an understanding of the role of chemistry in our daily lives and in the '
                           'world around us.</p>',
               'old_introduction': 'Chemistry is the branch of science that deals with the composition, '
                                   'structure, and properties of matter, as well as the changes it undergoes '
                                   'during chemical reactions.…',
               'body': '<p>Chemistry helps you understand what matter is made of, how substances behave and '
                       'what happens when they react. Your learning introduces atomic structure, chemical '
                       'bonding, chemical reactions and the periodic table.</p><p>Through classroom learning '
                       'and laboratory experiments, you practise investigating, thinking critically and '
                       'solving problems while connecting chemistry to daily life.</p>',
               'introduction': 'Explore atoms, chemical bonds, reactions and the periodic table to '
                               'understand the substances around you.'},
 'physics': {'title': 'Physics',
             'old_body': '<p>Physics is the scientific study of matter and energy and their interactions '
                         'with each other in the universe. In this curriculum, physics introduces students '
                         'to the basic principles of physics, including motion, energy, forces, waves, and '
                         'electromagnetism. The course involves conducting experiments, analyzing data, and '
                         'making predictions based on observations and mathematical models. Through physics, '
                         'students develop critical thinking skills and learn to use scientific methods to '
                         'investigate natural phenomena. Additionally, physics helps students understand the '
                         'world around them, from the behaviour of everyday objects to the workings of '
                         'complex systems, such as machines, electricity, and the universe.</p>',
             'old_introduction': 'Physics is the scientific study of matter and energy and their '
                                 'interactions with each other in the universe. In this curriculum, physics '
                                 'introduces students to the…',
             'body': '<p>In Physics, you explore matter, energy and their interactions. You study motion, '
                     'forces, energy, waves and electromagnetism, connecting these ideas to everyday objects '
                     'and systems.</p><p>You conduct experiments, analyse data and make predictions using '
                     'observations and mathematical models. This helps you develop your scientific reasoning '
                     'and understand phenomena such as electricity and the workings of machines.</p>',
             'introduction': 'Investigate motion, forces, energy, waves and electromagnetism to understand '
                             'how the physical world works.'},
 'biology': {'title': 'Biology',
             'old_body': '<p>Biology is the scientific study of living organisms and their interactions with '
                         'their environment. In this curriculum, biology provides a foundational '
                         'understanding of life processes and the diversity of living organisms. The course '
                         'covers topics such as cell biology, genetics, evolution, etc. Through laboratory '
                         'experiments and classroom lectures, students develop an understanding of the '
                         'scientific methods, critical thinking skills, and an appreciation for the '
                         'complexity and interconnectedness of living systems. Biology is relevant to '
                         'everyday life and helps students understand the impact of human activity on the '
                         'natural world. Furthermore, biology provides a basis for understanding health and '
                         'medicine, as well as the potential for scientific advancements in biotechnology '
                         'and environmental conservation.</p>',
             'old_introduction': 'Biology is the scientific study of living organisms and their interactions '
                                 'with their environment. In this curriculum, biology provides a '
                                 'foundational understanding of life processes and…',
             'body': '<p>Biology introduces you to life processes and the diversity of living organisms. You '
                     'explore topics such as cells, genetics and evolution, and consider how organisms '
                     'interact with their environment.</p><p>Through laboratory work and classroom learning, '
                     'you practise scientific methods and critical thinking. You also connect your '
                     'understanding of living systems to health, medicine and the impact of human activity '
                     'on the natural world.</p>',
             'introduction': 'Discover how living organisms function, develop and interact with their '
                             'environment, from cells and genetics to evolution.'},
 'english-literature': {'title': 'English Literature',
                        'old_body': '<p>English literature is the study of literary works written in the '
                                    'English language, from different time periods and cultures. In this '
                                    "curriculum, English literature aims to develop students' critical "
                                    'reading and analytical skills, as well as their ability to communicate '
                                    'effectively in written and spoken forms. The course covers a range of '
                                    'genres, including poetry, drama, and prose, and focuses on analyzing '
                                    'literary techniques and devices, themes, and historical and cultural '
                                    'contexts. Students also learn to analyze and interpret the meanings and '
                                    'significance of literary works, and to appreciate the value of '
                                    'literature as a reflection of human experiences and perspectives. '
                                    'Through studying English literature, students can develop a deeper '
                                    'understanding of the world around them and gain insights into the human '
                                    'condition.</p>',
                        'old_introduction': 'English literature is the study of literary works written in '
                                            'the English language, from different time periods and cultures. '
                                            'In this curriculum, English literature aims to…',
                        'body': '<p>In English Literature, you read works from different periods and '
                                'cultures, including poetry, drama and prose. You explore literary '
                                'techniques, themes and the historical and cultural settings that shape a '
                                'text.</p><p>You learn to interpret meaning, support your ideas through '
                                'close reading and communicate your response in writing and discussion. '
                                'Literature gives you opportunities to consider human experiences and '
                                'perspectives beyond your own.</p>',
                        'introduction': 'Read poetry, drama and prose, explore different perspectives, and '
                                        'develop your own thoughtful interpretations of literary works.'},
 'religious-studies': {'title': 'Religious Studies',
                       'old_body': '<p>As a Christian educational institution in Lesotho, Religious studies '
                                   'is a very important subject to us. It encompasses the study of the '
                                   'beliefs, practices, and history of the Christian faith. In this high '
                                   'school curriculum, religious studies aims to provide students with an '
                                   'understanding of the central tenets of Christianity, as well as the '
                                   'diversity of Christian traditions and practices. The course covers '
                                   'topics such as the life and teachings of Jesus, the history of '
                                   'Christianity, the Bible, Christian ethics and morality, and the role of '
                                   'religion in society. Through studying religious studies, students can '
                                   'develop an appreciation for the cultural and historical significance of '
                                   'Christianity, as well as an understanding of the ways in which religion '
                                   'influences human behavior and societal values. Additionally, religious '
                                   'studies can help students develop their critical thinking skills and '
                                   'gain a deeper understanding of their own beliefs and values.</p>',
                       'old_introduction': 'As a Christian educational institution in Lesotho, Religious '
                                           'studies is a very important subject to us. It encompasses the '
                                           'study of the beliefs, practices, and history…',
                       'body': '<p>Religious Studies introduces you to the beliefs, practices and history of '
                               'the Christian faith. You explore the life and teachings of Jesus, the Bible, '
                               'Christian traditions, ethics and morality.</p><p>You consider the role of '
                               'religion in society and how beliefs influence behaviour and shared values. '
                               'Along the way, you develop your critical thinking and reflect on your own '
                               'understanding of faith and responsibility.</p>',
                       'introduction': 'Explore Christian beliefs, history and traditions, and reflect on '
                                       'faith, ethics and your own values.'},
 'economics': {'title': 'Economics',
               'old_body': '<p>Economics is the social science that studies how people allocate resources to '
                           'satisfy their wants and needs. In this curriculum, economics aims to introduce '
                           'students to the basic concepts and principles of economics, such as supply and '
                           'demand, market structures, and the role of government in the economy. The course '
                           'also covers topics such as international trade, economic growth, inflation, and '
                           'unemployment. Through studying economics, students can develop an understanding '
                           'of how markets work, how businesses make decisions, and how individuals make '
                           'choices in a world of scarce resources. Additionally, economics can help '
                           'students understand the impact of economic policies on society and the role of '
                           'government in regulating economic activity. Economics is relevant to many '
                           'aspects of daily life, such as personal finance, consumer behaviour, and public '
                           'policy, and can provide a foundation for further study in business, finance, and '
                           'public policy.</p>',
               'old_introduction': 'Economics is the social science that studies how people allocate '
                                   'resources to satisfy their wants and needs. In this curriculum, '
                                   'economics aims to introduce students to…',
               'body': '<p>Economics helps you investigate how people use limited resources to meet their '
                       'needs and wants. You study supply and demand, market structures and the role of '
                       'government in the economy.</p><p>Your learning also explores international trade, '
                       'economic growth, inflation and unemployment. You connect these ideas to business '
                       'decisions, personal finance and the effects of economic policy on society.</p>',
               'introduction': 'Understand how people, businesses and governments make choices about '
                               'resources, and explore the forces that shape an economy.'},
 'accounting': {'title': 'Accounting',
                'old_body': '<p>Accounting is the process of recording, classifying, and summarise financial '
                            'transactions to provide information that is useful for decision-making '
                            'purposes. In this curriculum, accounting aims to introduce students to the '
                            'basic concepts and principles of financial accounting, such as the accounting '
                            'equation, financial statements, and the role of accounting in business. The '
                            'course covers topics such as balance sheets, income statements, cash flow '
                            'statements, and the principles of accounting. Through studying accounting, '
                            'students develop skills in financial analysis, record keeping, and financial '
                            'reporting. Additionally, accounting provides a foundation for understanding the '
                            'financial aspects of personal and business decision-making, such as budgeting, '
                            'investing, and financial planning. Accounting is relevant to many aspects of '
                            'daily life, such as personal finance and entrepreneurship, and can provide a '
                            'pathway for students interested in pursuing careers in accounting, finance, or '
                            'business management.</p>',
                'old_introduction': 'Accounting is the process of recording, classifying, and summarise '
                                    'financial transactions to provide information that is useful for '
                                    'decision-making purposes. In this curriculum, accounting aims to…',
                'body': '<p>In Accounting, you learn how financial transactions are recorded, classified and '
                        'summarised. You explore the accounting equation and financial statements, including '
                        'balance sheets, income statements and cash flow statements.</p><p>You build skills '
                        'in record keeping, financial analysis and reporting, and consider how accounting '
                        'supports decisions about budgeting, investing and the running of a business.</p>',
                'introduction': 'Learn to record and interpret financial transactions, prepare financial '
                                'statements and use accounting information to make informed decisions.'},
 'information-communication-and-technology-ict': {'title': 'Information, Communication and Technology (ICT)',
                                                  'old_body': '<p>Information, communication, and technology '
                                                              '(ICT) refers to the use of technology to '
                                                              'create, process, store, and exchange '
                                                              'information. In this curriculum, ICT aims to '
                                                              'introduce students to the basic concepts and '
                                                              'principles of technology, such as hardware, '
                                                              'software, networks, and the internet. Through '
                                                              'hands-on experiences, students develop skills '
                                                              'in using a range of software and hardware '
                                                              'tools, as well as in problem-solving, '
                                                              'critical thinking, and communication. '
                                                              'Additionally, ICT provides a foundation for '
                                                              'understanding the role of technology in '
                                                              'society, including the impact of technology '
                                                              'on the economy, culture, and the environment. '
                                                              'ICT is relevant to many aspects of daily '
                                                              'life, such as communication, entertainment, '
                                                              'and education, and can provide a pathway for '
                                                              'students interested in pursuing careers in '
                                                              'technology, engineering, or computer '
                                                              'science.</p>',
                                                  'old_introduction': 'Information, communication, and '
                                                                      'technology (ICT) refers to the use of '
                                                                      'technology to create, process, store, '
                                                                      'and exchange information. In this '
                                                                      'curriculum, ICT aims to introduce '
                                                                      'students…',
                                                  'body': '<p>ICT introduces you to the technology used to '
                                                          'create, process, store and exchange information. '
                                                          'You explore hardware, software, networks and the '
                                                          'internet, and practise using a range of digital '
                                                          'tools.</p><p>Through practical work, you develop '
                                                          'your problem-solving and communication skills. '
                                                          'You also consider how technology affects the '
                                                          'economy, culture, the environment and everyday '
                                                          'life.</p>',
                                                  'introduction': 'Develop practical skills with digital '
                                                                  'tools and explore how hardware, software, '
                                                                  'networks and the internet help us work '
                                                                  'with information.'},
 'fashion-and-textiles': {'title': 'Fashion and Textiles',
                          'old_body': '<p>The objectives of studying Fashion and Textiles typically revolve '
                                      'around developing practical skills, fostering creativity, and '
                                      'building knowledge of the fashion industry and its related fields. '
                                      'Students gain skills in areas like fashion design, textile '
                                      'construction, and digital textile techniques. Beyond technical '
                                      'skills, the subject aims to cultivate critical thinking, '
                                      'problem-solving, and a deeper understanding of cultural and '
                                      'historical influences on fashion. This includes learning to use tools '
                                      'and equipment safely, mastering construction techniques like sewing '
                                      'and stitching, and developing proficiency in various textile '
                                      'techniques. Students are encouraged to experiment with different '
                                      'materials, design concepts, and creative expression through projects '
                                      'and assignments. The subject aims to provide students with a broad '
                                      'understanding of different areas within the fashion industry, '
                                      'including design, manufacturing, and marketing. Students learn to '
                                      'analyse fashion trends, evaluate designs, and address challenges in '
                                      'the design and production process. Students explore various fabrics, '
                                      'their characteristics, and how they can be manipulated and used '
                                      'creatively. Students gain insights into the social, economic, and '
                                      'cultural contexts that shape fashion trends. The subject can equip '
                                      'students with skills and knowledge relevant to various careers in the '
                                      'fashion and textile industries, including design, manufacturing, and '
                                      'retail.</p>',
                          'old_introduction': 'The objectives of studying Fashion and Textiles typically '
                                              'revolve around developing practical skills, fostering '
                                              'creativity, and building knowledge of the fashion industry '
                                              'and its related fields.…',
                          'body': '<p>In Fashion and Textiles, you explore fabrics, their characteristics '
                                  'and ways to use them creatively. You develop skills in design and textile '
                                  'construction, including sewing and stitching, while learning to use tools '
                                  'and equipment safely.</p><p>Your projects give you opportunities to '
                                  'experiment with materials and ideas, evaluate designs and solve '
                                  'production challenges. You also examine fashion trends and the cultural, '
                                  'historical and economic influences that shape them.</p>',
                          'introduction': 'Explore fabrics, design and textile construction, and develop '
                                          'your creativity through practical projects and safe use of '
                                          'tools.'},
 'food-and-nutrition': {'title': 'Food and Nutrition',
                        'old_body': '<p>Learning objectives in food and nutrition education focus on both '
                                    'knowledge and skills related to healthy eating, nutrition, and food '
                                    'systems. Students should be able to understand essential nutrients, '
                                    'their roles in health, and how to make informed food choices. '
                                    'Additionally, they should develop practical skills like planning and '
                                    'preparing healthy meals, and understanding the connection between food '
                                    'and health. Define key nutrients (proteins, carbohydrates, fats, '
                                    'vitamins, minerals, water) and their functions in the body. Identify '
                                    'different food groups and understand the recommended portion sizes for '
                                    'healthy eating. Explain the concept of a balanced diet and its '
                                    'importance in maintaining health. Relate nutritional needs to different '
                                    'life stages (e.g., childhood, adolescence, pregnancy, older adults). '
                                    'Analyse the social, cultural, and environmental factors that shape food '
                                    'choices. Understand the principles of food safety and hygiene to '
                                    'prevent food borne illnesses. Recognise the link between diet, health, '
                                    'and disease prevention. Understand different food systems and their '
                                    'impact on nutrition, health, and the environment.</p>',
                        'old_introduction': 'Learning objectives in food and nutrition education focus on '
                                            'both knowledge and skills related to healthy eating, nutrition, '
                                            'and food systems. Students should be able to…',
                        'body': '<p>Food and Nutrition helps you understand essential nutrients, food groups '
                                'and the importance of a balanced diet. You explore how nutritional needs '
                                'change at different stages of life and how social, cultural and '
                                'environmental factors influence food choices.</p><p>You develop skills in '
                                'planning and preparing healthy meals, alongside food safety and hygiene. '
                                'You also examine the connections between food, health and the wider food '
                                'systems that affect people and the environment.</p>',
                        'introduction': 'Understand nutrients and balanced diets, make informed food '
                                        'choices, and build practical skills in meal planning, preparation '
                                        'and food hygiene.'}}


def learner_curriculum_copy(body, introduction):
    if body == CURRICULUM_COPY['old_body']:
        body = CURRICULUM_COPY['body']
    if introduction == CURRICULUM_COPY['old_introduction']:
        introduction = CURRICULUM_COPY['introduction']
    return body, introduction


def learner_subject_copy(slug, body, introduction):
    copy = SUBJECT_COPY.get(slug)
    if copy:
        if body == copy['old_body']:
            body = copy['body']
        if introduction == copy['old_introduction']:
            introduction = copy['introduction']
    return body, introduction
