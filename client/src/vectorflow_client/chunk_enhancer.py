import os
import json
import tiktoken
import concurrent.futures
import datetime
import uuid
from openai import OpenAI
from posthog import Posthog

class ChunkEnhancer:
    def __init__(self, usecase, openai_api_key, model="gpt-4", number_of_questions=5):
        os.environ['OPENAI_API_KEY'] = openai_api_key
        self.client = OpenAI()
        
        # What is the use case for this search system? Please enter a description. The more you detail provide, the better.
        self.usecase = usecase 
        self.number_of_questions = number_of_questions
        self.model = model
        self.posthog = Posthog(project_api_key='phc_E2V9rY1esOWV6el6WjfGSiwhTj49YFXe8vHv1rcgx9E', host='https://eu.posthog.com')

        # chunk enhancement
        self.enhancement_system_prompt = "You are a helpful assistant."
        self.enhancement_user_prompt = """
            Given the following excerpt from a document and a json object containing of pieces of information extracted from the whole document, 
            select the 5 pieces of information most relevant to the excerpt.

            If a piece of information is already contained in the document excerpt, do not select it. 
            For example, if the JSON has the entity "John Smith" and the excerpt is "John Smith is a great guy", do not select "John Smith".

            Do not add whole sentences, only phrases or clauses or words that improve the searchability of the piece of information.
            Do not alter the original excerpt, add new information to the end.

            The selected information should be only items from the json object.

            Return JSON with the added information represented as a list of strings, comma separated like this:
            enhancements: "info1,info 2,info3,info4,info5" 

            ### Extracted Information About Document
            {document_context}

            ### Excerpt:
            {chunk}
            """
        
        # use case specific extraction
        self.usecase_system_prompt = "You are an assistant whose speciality is generating questions about a given use case for a search system."
        self.usecase_user_prompt = """Given the following scenario, generate {num_questions} questions that a user might ask about the scenario.
            Output the information as JSON, with the questions as a list of strings marked by the key 'questions'.

            For example, if the use case is "I am a real estate agent reviewing template lease agreements to find the best one", the list of questions could be:
            ['What lease agreement has the best terms for landlords',
            'What lease agreement has the best terms for tenants',
            'Which lease agreements have detailed information about pets',
            'Do any of the leases discuss eviction?',
            'What are the common types of payment methods in the lease agreements?',
            'Can you give me a summary of the lease agreements?',
            'Do any of the leases have sections discussing tenant refunds?']

            ### Use Case:
            {usecase}

            ### Output:
            """
        
        self.usecase_enhancement_system_prompt = "You are an assistant whose speciality is extracting information from documents for answering specific types of questions."
        self.usecase_enhancement_user_prompt = """Given the following document and a list of sample questions, 
            extract important information from it such as entities, keywords, themes, labels, sections or chapters of document, etc that will be useful for answering questions similar to samples. 
            Output the information as JSON. 

            ### Sample Questions:
            {questions}

            ### Document:
            {document}

            ### Output:
            """
        
        # whole document extraction
        self.whole_document_extraction_user_prompt = """
            Given the following document, extract important information from it such as entities, keywords, themes, labels, sections or chapters of document, etc that will be useful for answering questions about the document. 
            Output the information as JSON. 

            ### Document:
            {document}

            ### Output:
            """
            
    def enhance_chunks(self, chunks, document):
        questions_json = self.generate_questions_from_usecase()
        context_json = self.get_context_about_questions(document=document, questions=questions_json['questions'])
        enhanced_chunks = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            enhanced_chunks = list(executor.map(lambda chunk: self.enhance_chunk(chunk, context_json), chunks))

        summary = self.summarize(document=document)
        enhanced_chunks.append(summary['summary'])
        self.send_telemetry(len(enhanced_chunks))
        return enhanced_chunks

    def enhance_chunk(self, chunk, context_json):
        enhanced_chunk_json = self.get_chunk_enhancements(chunk, context_json)
        enhancement_string = ','.join(enhanced_chunk_json['enhancements'])
        enhanced_chunk = chunk + ", " + enhancement_string
        return enhanced_chunk
    
    def get_chunk_enhancements(self, chunk, context):
        user_prompt = self.enhancement_user_prompt.format(chunk=chunk, document_context=context)
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.enhancement_system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        content = completion.choices[0].message.content
        format_chunk_enhancements = {
            'name': 'format_chunk_enhancements',
            'description': 'Get a list of 5 relevant items about an exceprt from a document',
            'parameters': {
                'type': 'object',
                'properties': {
                    'enhancements': {
                        'type': 'array',
                        'items': {
                            'type': 'string' 
                        }
                    }
                }
            }
        }

        response = self.client.chat.completions.create(
            model = self.model,
            messages = [
                {"role": "system", "content": "You are a helpful assistance."},
                {'role': 'user', 'content': content}
            ],
            tools = [{'type': 'function', 'function': format_chunk_enhancements}],
            tool_choice={"type": "function", "function": {"name": "format_chunk_enhancements"}}
        )

        json_response = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
        print(f"Adding the following information to the end of thechunk:\n{json_response['enhancements']}")
        return json_response
    
    def generate_questions_from_usecase(self):
        user_prompt = self.usecase_user_prompt.format(usecase=self.usecase, num_questions=self.number_of_questions)
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.usecase_system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        content = completion.choices[0].message.content
        format_questions = {
            'name': 'format_questions',
            'description': 'Get the list of questions from the input text',
            'parameters': {
                'type': 'object',
                'properties': {
                    'questions': {
                        'type': 'array',
                        'items': {
                            'type': 'string' 
                        }
                    }
                }
            }
        }

        response = self.client.chat.completions.create(
            model = self.model,
            messages = [
                {"role": "system", "content": "You are a helpful assistance."},
                {'role': 'user', 'content': content}
            ],
            tools = [{'type': 'function', 'function': format_questions}],
            tool_choice={"type": "function", "function": {"name": "format_questions"}}
        )

        json_response = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
        print(f"Generated the following questions about the usecase:\n{json_response['questions']}")
        return json_response
    
    def get_context_about_questions(self, document, questions):
        extracted_document = self.extract_for_token_limit(document, questions=questions)
        user_prompt = self.usecase_enhancement_user_prompt.format(document=extracted_document, questions=questions)
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.usecase_enhancement_system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        content = completion.choices[0].message.content
        format_content_from_questions = {
            'name': 'format_content_from_questions',
            'description': 'Get the information extracted from a document that is in the input text',
            'parameters': {
                'type': 'object',
                'properties': {
                    'entities': {
                        'type': 'array',
                        'items': {
                            'type': 'string' 
                        }
                    },
                    'keywords': {
                        'type': 'array',
                        'items': {
                            'type': 'string' 
                        }
                    },
                    'sections': {
                        'type': 'array',
                        'items': {
                            'type': 'string' 
                        }
                    },
                    'themes': {
                        'type': 'array',
                        'items': {
                            'type': 'string' 
                        }
                    },
                    'labels': {
                        'type': 'array',
                        'items': {
                            'type': 'string' 
                        }
                    },
                    'other': {
                        'type': 'array',
                        'items': {
                            'type': 'string' 
                        }
                    }
                }
            }
        }

        response = self.client.chat.completions.create(
            model = self.model,
            messages = [
                {"role": "system", "content": "You are a helpful assistance."},
                {'role': 'user', 'content': content}
            ],
            tools = [{'type': 'function', 'function': format_content_from_questions}],
            tool_choice={"type": "function", "function": {"name": "format_content_from_questions"}}
        )

        json_response = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
        return json_response 
    
    def extract_for_token_limit(self, document, questions):
        encoding = tiktoken.encoding_for_model(self.model)
        question_string = ",".join(questions)
        questions_count = len(encoding.encode(question_string))
        user_prompt_count = len(encoding.encode(self.usecase_enhancement_user_prompt))
        system_prompt_count = len(encoding.encode(self.usecase_enhancement_system_prompt))
        extra_count = len(encoding.encode("'role', 'system', 'content', 'role', 'user', 'content'"))
        token_limit = 8192

        if "16k" in self.model:
            token_limit = 16384
        elif "32k" in self.model:
            token_limit = 32768

        remaining_tokens = token_limit - (questions_count + user_prompt_count + system_prompt_count + extra_count)
        document_encoding = encoding.encode(document)
        if len(encoding.encode(document)) <= remaining_tokens:
            return document
        
        #return encoding.decode(document_encoding[:remaining_tokens])
        return document[:remaining_tokens*3]
    
    def summarize(self, document):
        extracted_document = self.extract_for_token_limit(document, questions=[])
        summary_prompt = """
            Given the following document, summarize it in 5-8 sentences.
            Output the summary as a string.

            ### Document:
            {document}

            ### Summary:
            """
        user_prompt = summary_prompt.format(document=extracted_document)
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.enhancement_system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        content = completion.choices[0].message.content
        format_summary = {
            'name': 'format_summary',
            'description': 'Get a summary of a document and format it',
            'parameters': {
                'type': 'object',
                'properties': {
                    'summary': {
                        'type': 'string',
                    }
                }
            }
        }

        response = self.client.chat.completions.create(
            model = self.model,
            messages = [
                {"role": "system", "content": self.enhancement_system_prompt},
                {'role': 'user', 'content': content}
            ],
            tools = [{'type': 'function', 'function': format_summary}],
            tool_choice={"type": "function", "function": {"name": "format_summary"}}
        )

        json_response = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
        return json_response
    
    def get_whole_document_context(self, document):
        extracted_document = self.extract_for_token_limit(document, questions=[])
        user_prompt = self.whole_document_extraction_user_prompt.format(document=extracted_document)
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.enhancement_system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        content = completion.choices[0].message.content
        format_document_context = {
            'name': 'format_document_context',
            'description': 'Get the information extracted from a document that is in the input text',
            'parameters': {
                'type': 'object',
                'properties': {
                    'entities': {
                        'type': 'array',
                        'items': {
                            'type': 'string' 
                        }
                    },
                    'keywords': {
                        'type': 'array',
                        'items': {
                            'type': 'string' 
                        }
                    },
                    'sections': {
                        'type': 'array',
                        'items': {
                            'type': 'string' 
                        }
                    },
                    'themes': {
                        'type': 'array',
                        'items': {
                            'type': 'string' 
                        }
                    },
                    'labels': {
                        'type': 'array',
                        'items': {
                            'type': 'string' 
                        }
                    },
                    'other': {
                        'type': 'array',
                        'items': {
                            'type': 'string' 
                        }
                    }
                }
            }
        }

        response = self.client.chat.completions.create(
            model = self.model,
            messages = [
                {"role": "system", "content": self.enhancement_system_prompt},
                {'role': 'user', 'content': content}
            ],
            tools = [{'type': 'function', 'function': format_document_context}],
            tool_choice={"type": "function", "function": {"name": "format_document_context"}}
        )

        json_response = json.loads(response.choices[0].message.tool_calls[0].function.arguments)
        return json_response

    def send_telemetry(self, number_of_chunks, event_name="ENHANCE_CHUNKS"):
        if os.getenv("TELEMETRY_DISABLED"):
            return
        
        user_id = str(uuid.uuid4())
        current_time = datetime.datetime.now()
        properties = {
            "time": current_time.strftime('%m/%d/%Y'),
            "model": self.model,
            "usecase": self.usecase,
            "number_of_chunks":  number_of_chunks,
        }

        try:
            self.posthog.capture(user_id, event_name, properties)
        except Exception as e:
            print('ERROR sending telemetric data to Posthog. See exception: %s', e)
