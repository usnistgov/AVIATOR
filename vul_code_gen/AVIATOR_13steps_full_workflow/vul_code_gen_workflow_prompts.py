BENIGN_CODE_ANALYZER_TEMPLATE="""Your task is to analyze the benign function below and try to better understand its goals and its code structure.
{benign_code}

Return your response as a valid JSON object with exactly the following parameters, maintaining correct types:
- "function_purpose": (str) Provide a proper description of what the code above is intended to do.
- "input_descriptions": (list[dict[str, str]]) List descriptions explaining all input arguments and what they are used for. Return a JSON list of dictionary, for example [{{"input name": "A string used for ..."}}].
- "output_descriptions": (list[dict[str, str]]) List descriptions explaining all return values.
- "source_sink_list": (list[str]) Exhaustive list of pairs of corresponding code sources and sinks. A source is a data-entry point (e.g., user input), and a sink is a function that should not be called with unsanitized, untrusted data. One source van have multiple sinks and vis-versa, but list them only by pairs. For example [["name of source 1", "name of sink 1"], ["name of source 2", "name of sink 2"], ["name of source 3", "name of sink 3"]]
- "data_flows": (list[str]) Analyze and describe all the steps of how data propagates between sources and sinks and throughout the whole code. Return a JSON list, where each line is a textual description of all the steps the data follows between one source and one sink. Do this also throughout the entire code.

Do not repeat yourself.
Ensure to write the JSON object in between these markers ```json and ```"""


SANITIZATION_DETECTOR_TEMPLATE = """Your task is to identify sanitization and vulnerability mitigation elements that makes the code below benign.

The benign source code to analyze is:
{benign_code}

The purpose of this code is described as: {function_purpose}
Its inputs are: {input_descriptions}
Its inputs are: {output_descriptions}

Use the following list of sources / sinks and dataflow as starting point to identify the different ways the vulnerability described in vul_inject_info is avoided in this benign source code:
- "source_sink_list": {source_sink_list} 
- "data_flows": {data_flows} 

The vulnerability that is prevented in this code can be described as follows:
{vul_inject_info}


Return your response as a valid JSON object with exactly the following parameters, maintaining correct types:
- "sanitization": (list[dict[str, str]]) Identify and analyze all sanitization and vulnerability mitigation elements that make the benign code actually non-vulnerable in terms of the vulnerability described above. Return a JSON list of dictionaries [{{"description": "Actual explanation here", "code": "corresponding code here"}}]

Important:
- Do not include any additional text or formatting outside the JSON object.
- Ensure the JSON strictly adheres to the specified parameter names and types.
- Ensure to write the JSON object in between these markers ```json
{{
  "sanitization": [
    {{"description": "Actual explanation here", "code": "corresponding code here"}},
    ...
  ]
}}
and ```
- Be sure to close every string you open with "
- Do not ever repeat yourself.

Now, please generate the JSON assessment."""


VUL_INJECTOR_TEMPLATE = """Your task is to modify the source code of non-vulnerable function below to introduce the requested vulnerability.

The non-vulnerable code that must be modified to introduce changes that will make this code vulnerable is:
{benign_code}

The purpose of this code is described as: {function_purpose}

Its data flows are: {data_flows}

The list of sanitization and vulnerability mitigation elements that made the benign code actually non-vulnerable are:
{sanitization}


Think step by step and leverage the previous analysis of the code to change the code to introduce this vulnerability: {vul_inject_info}


As a model you can leverage these examples of how a benign code was modified to introduce the vulnerability {vul_inject_id}:
{retrieved_context}


Return your response as a valid JSON object with exactly the following parameters, maintaining correct types:
- "vulnerable_code": (str) Modified source code with vulnerability introduced. Write your code in between these tags <raw> full vulnerable code </raw>. Rewrite the full code, do not truncate by adding comments such as "//... rest of the code...". Do not add comments indicating where the vulnerability was introduced.

Important:
- Do not include any additional text or formatting outside the JSON object.
- Ensure the JSON strictly adheres to the specified parameter names and types.
- Ensure to write the JSON object in between these markers ```json and ```
- Ensure to write the code in between these tags <raw> full vulnerable code </raw>
- Write the code for the full function with modifications where the original benign code is changed to introduce a new vulnerability. 
- Output only a valid JSON object. Do not include markdown formatting (no triple backticks or extra quotes). Please ensure that any internal quotes are escaped properly.
- Do not ever repeat yourself.

Now, please modify the benign function accordingly and output only the JSON object as specified. Be sure to finish the JSON with ```"""


VUL_CODE_LLM_CHECKER_TEMPLATE = """You are tasked to verify that the benign code below has been properly modified to introduce the CWE vulnerability {vul_inject_id}.

The initial non-vulnerable source code function was:
{benign_code}

The new version of the code that must have been modified to introduce changes that supposedly make this code vulnerable:
{vulnerable_code}

Verify that the code was properly modified to introduce the following vulnerability: {vul_inject_info}.

You must ask yourself the following questions and think step by step as an expert:
- You claimed that introducing the following changes would transform the code to become vulnerable. Does this really introduces the CWE vulnerability {vul_inject_id} and actually modifies the code?
- If yes, did you actually made the change? Are you sure?
- If no, can you modify the initial non-vulnerable source code function to introduce the requested vulnerability. 
- Either way, verify that the vulnerability was introduced in a realistic way, as if a human developer had made a mistake. 
- Make sure the code still makes sense and did not loose its functionality.
- Have you truncated the code to only show the modifications? The vulnerable code should show the full code.

If you need to make some modifications, rewrite the values. Otherwise, if everything is correct, return the values without changes.

Return your response as one valid JSON object with exactly the following parameters, maintaining correct types:
- "vulnerable_code": (str) Modified source code with vulnerability introduced. Write your code in between these tags <raw> full vulnerable code </raw>. Make sure you checked the questions above and the code is properly vulnerable.
- "injection_location": (str) Location where you have modified the code to introduce the vulnerability (line number, function section and explanation of the location).
- "injection_justification": (str) Detailed explanation of why you have modified the code to introduce this vulnerability in this specific way, referencing function analysis and retrieved context.
- "confidence_score": (int) Score between 0 and 10 on how confident you are that your answer is correct and the vulnerable code actually is vulnerable with the proper vulnerability.
- "confidence_justification": (str) Justification of the confidence score. 

Important:
- Do not include any additional text or formatting outside the JSON object.
- Ensure the JSON strictly adheres to the specified parameter names and types. Do not write the types.
- Ensure to write the JSON object in between these markers ```json and ```
- Output only a valid JSON object. Do not include markdown formatting (no triple backticks or extra quotes). Please ensure that any internal quotes are escaped properly.
- Do not ever repeat yourself.

Now, please make the verifications and output only the JSON object as specified."""


CRITICAL_ANALYZER_TEMPLATE = """You need to critically analyze the code changes made to introduce a vulnerability and verify that they properly implement the intended vulnerability type.

The original benign code was:
{benign_code}

The vulnerable code that was produced is:
{vulnerable_code}

The difference between the benign and vulnerable code is shown below with [ADDED] and [REMOVED] markers:
{code_diff}

The vulnerability that should have been introduced is:
{vul_inject_id}: {vul_inject_info}

You are claiming to have made the following modification:
- Location: {injection_location}
- Justification: {injection_justification}

Your task is to critically analyze whether:
1. The modifications actually match what was claimed in the injection_location
2. The introduced changes actually correspond to the vulnerability described in vul_inject_info
3. The vulnerability has been properly implemented, not just superficially simulated
4. The code changes are substantive and not merely cosmetic

Return your response as a valid JSON object with exactly the following parameters, maintaining correct types:
- "analysis_result": (str) Your detailed critical analysis explaining whether the code modification properly introduces the intended vulnerability. Include specific references to the code changes and vulnerability requirements.
- "modification_valid": (bool) A boolean value indicating whether the modification properly introduces the intended vulnerability (true) or if it fails to do so (false).

Important:
- Do not include any additional text or formatting outside the JSON object.
- Ensure the JSON strictly adheres to the specified parameter names and types.
- Ensure to write the JSON object in between these markers ```json and ```
- Be critical and thorough in your assessment - the goal is to verify that the vulnerability was properly introduced.
- Do not ever repeat yourself.

Now, please analyze the code changes and provide your assessment as specified."""


VULNERABILITY_VERIFIER_TEMPLATE = """You are a comprehensive vulnerability verification system with advanced knowledge of common programming flaws, security issues, and code vulnerabilities.

You need to perform a final validation of whether the vulnerability has been properly introduced in the code, using all available evidence.

The original benign code was:
{benign_code}

The vulnerable code that was produced is:
{vulnerable_code}

The intended vulnerability to introduce was:
{vul_inject_id}: {vul_inject_info}

You have the following assessments about the vulnerability introduction:
1. Critical analysis result: {analysis_result}
2. Modification was judged valid: {modification_valid}

Static analysis of the code produced these results:
- CWE IDs detected: {cwe_ids}
- Static analysis errors: {static_analysis_errors}

The difference between the benign and vulnerable code is shown below with [ADDED] and [REMOVED] markers:
{code_diff}

You are claiming to have made the following modification:
- Location: {injection_location}
- Justification: {injection_justification}

Your task is to provide a final verification of whether the vulnerability was successfully introduced:
1. Evaluate whether the CWE detection matches the intended vulnerability type
2. Cross-reference the code changes with the static analysis findings
3. Determine if the vulnerable code exhibits the security weakness described in the vulnerability description
4. Verify that the code modification is both realistic and meaningful
5. Confirm that the intended vulnerable pattern has been implemented correctly

Return your response as a valid JSON object with exactly the following parameters, maintaining correct types:
- "is_correctly_vulnerable": (bool) A boolean value indicating whether the code correctly implements the intended vulnerability.
- "verification_explanation": (str) A detailed explanation of your verification process and conclusions, including evidence from the static analysis, code diff, and previous assessments.

Important:
- Do not include any additional text or formatting outside the JSON object.
- Ensure the JSON strictly adheres to the specified parameter names and types.
- Ensure to write the JSON object in between these markers ```json and ```
- Be comprehensive and thorough in your final assessment.
- Do not ever repeat yourself.

Now, please provide your final verification of the vulnerability introduction as specified."""


IDENTICAL_CODE_VUL_INJECTOR_TEMPLATE = """You are tasked with introducing a vulnerability into the code below. The previous attempt produced code that was identical to the original benign code, so the requested vulnerability was NOT introduced. You must now explicitly modify the code to introduce the vulnerability described below.

The original benign code is:
{benign_code}

The vulnerability to introduce is:
{vul_inject_id}: {vul_inject_info}

The purpose of this code is described as: {function_purpose}

Its data flows are: {data_flows}

The list of sanitization and vulnerability mitigation elements that made the benign code non-vulnerable are:
{sanitization}

As a model you can leverage these examples of how a benign code was modified to introduce the vulnerability {vul_inject_id}:
{retrieved_context}

Return your response as a valid JSON object with exactly the following parameters, maintaining correct types:
- "vulnerable_code": (str) Modified source code with the vulnerability introduced. Write your code in between these tags <raw> full vulnerable code </raw>. Rewrite the full code, do not truncate by adding comments such as "//... rest of the code...". Do not add comments indicating where the vulnerability was introduced.
- "injection_location": (str) Location where you have modified the code to introduce the vulnerability (line number, function section and explanation of the location).
- "injection_justification": (str) Detailed explanation of why you have modified the code to introduce this vulnerability in this specific way, referencing function analysis and retrieved context.
- "confidence_score": (int) Score between 0 and 10 on how confident you are that your answer is correct and the vulnerable code actually is vulnerable with the proper vulnerability.
- "confidence_justification": (str) Justification of the confidence score. 

Important:
- Do not include any additional text or formatting outside the JSON object.
- Ensure the JSON strictly adheres to the specified parameter names and types.
- Ensure to write the JSON object in between these markers ```json and ```
- Ensure to write the code in between these tags <raw> full vulnerable code </raw>
- Write the code for the full function with modifications where the original benign code is changed to introduce a new vulnerability. 
- Output only a valid JSON object. Do not include markdown formatting (no triple backticks or extra quotes). Please ensure that any internal quotes are escaped properly.
- Do not ever repeat yourself.

Now, please modify the benign function accordingly and output only the JSON object as specified. Be sure to finish the JSON with ```
"""

VUL_DIFF_CHECKER_TEMPLATE = """You are tasked with verifying that the changes made to the code below actually correspond to the requested vulnerability and that the generated vulnerable code is not missing any parts from the original code that would change its functionality.

The original benign code is:
{benign_code}

The vulnerable code that was produced is:
{vulnerable_code}

The vulnerability to introduce is:
{vul_inject_id}: {vul_inject_info}

The purpose of this code is described as: {function_purpose}

Its data flows are: {data_flows}

The list of sanitization and vulnerability mitigation elements that made the benign code non-vulnerable are:
{sanitization}

Your tasks:
1. Analyze the differences between the benign and vulnerable code.
2. Ensure that the changes made actually introduce the requested vulnerability.
3. Ensure that the vulnerable code is not missing any parts from the original code that would change its intended functionality.
4. If the changes are insufficient or incorrect, update the vulnerable code to properly introduce the vulnerability while preserving the original functionality.

Return your response as a valid JSON object with exactly the following parameters, maintaining correct types:
- "diff_analysis": (str) Analysis of whether the code changes correspond to the requested vulnerability and if any functionality is lost.
- "injection_location": (str) Location where you have modified the code to introduce the vulnerability (line number, function section and explanation of the location).
- "injection_justification": (str) Detailed explanation of why you have modified the code to introduce this vulnerability in this specific way, referencing function analysis and retrieved context.
- "confidence_score": (int) Score between 0 and 10 on how confident you are that your answer is correct and the vulnerable code actually is vulnerable with the proper vulnerability.
- "confidence_justification": (str) Justification of the confidence score. 

Important:
- Do not include any additional text or formatting outside the JSON object.
- Ensure the JSON strictly adheres to the specified parameter names and types.
- Ensure to write the JSON object in between these markers ```json and ```
- Ensure to write the code in between these tags <raw> full vulnerable code </raw>
- Output only a valid JSON object. Do not include markdown formatting (no triple backticks or extra quotes). Please ensure that any internal quotes are escaped properly.
- Do not ever repeat yourself.

Now, please analyze and, if needed, update the vulnerable code and output only the JSON object as specified. Be sure to finish the JSON with ```
"""

VULNERABILITY_FIXER_TEMPLATE = """You are a code vulnerability injection expert. The previous attempt to introduce the vulnerability was unsuccessful according to the following analysis:

- Vulnerability verification result: {verification_explanation}

- The difference between the benign and vulnerable code is shown below with [ADDED] and [REMOVED] markers:
{code_diff}

You also have the following information about the intended vulnerability:
- Vulnerability to introduce: {vul_inject_id}: {vul_inject_info}
- Function purpose: {function_purpose}
- Data flows: {data_flows}
- Sanitization and mitigation elements: {sanitization}

Your task is to carefully analyze all the above information and modify the code to ensure the intended vulnerability is actually present. Use the code diff and static analysis to guide your changes. Make sure the code is realistically vulnerable, not just superficially changed, and that it still makes sense and preserves its intended functionality.

Return your response as a valid JSON object with exactly the following parameters, maintaining correct types:
- "vulnerable_code": (str) Modified source code with vulnerability introduced. Write your code in between these tags <raw> full vulnerable code </raw>. Rewrite the full code, do not truncate by adding comments such as "//... rest of the code...". Do not add comments indicating where the vulnerability was introduced.
- "injection_location": (str) Location where you have modified the code to introduce the vulnerability (line number, function section and explanation of the location).
- "injection_justification": (str) Detailed explanation of why you have modified the code to introduce this vulnerability in this specific way, referencing function analysis and the verification/diff context.
- "confidence_score": (int) Score between 0 and 10 on how confident you are that your answer is correct and the vulnerable code actually is vulnerable with the proper vulnerability.
- "confidence_justification": (str) Justification of the confidence score. 

Important:
- Do not include any additional text or formatting outside the JSON object.
- Ensure the JSON strictly adheres to the specified parameter names and types. Do not write the types.
- Ensure to write the JSON object in between these markers ```json and ```
- Ensure to write the code in between these tags <raw> full vulnerable code </raw>
- Output only a valid JSON object. Do not include markdown formatting (no triple backticks or extra quotes). Please ensure that any internal quotes are escaped properly.
- Do not ever repeat yourself.

Now, please modify the function accordingly and output only the JSON object as specified. Be sure to finish the JSON with ```"
"""