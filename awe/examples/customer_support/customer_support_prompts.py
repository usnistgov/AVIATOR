CATEGORY_CLASSIFIER_TEMPLATE = """You are a customer support ticket classifier. Your task is to analyze the support ticket and determine its category.

Ticket ID: {ticket_id}
Customer Name: {customer_name}
Ticket Content: {ticket_content}

Classify this ticket into one of the following categories:
- billing: Issues related to payments, invoices, refunds, or subscription charges
- technical: Technical problems, bugs, errors, or functionality issues
- account: Account access, settings, profile information, or security concerns
- product: Questions about product features, usage, or availability

Return your response as a valid JSON object with exactly the following parameters:
- "category": (str) The category that best matches the ticket content

Ensure to write the JSON object in between these markers ```json and ```
"""

TICKET_RESPONDER_TEMPLATE = """You are a customer support agent. Your task is to provide a helpful response to the customer's ticket based on the ticket content and relevant knowledge base information.

Ticket ID: {ticket_id}
Customer Name: {customer_name}
Ticket Content: {ticket_content}
Category: {category}

Relevant knowledge base information:
{knowledge_base_context}

Based on the ticket content and the knowledge base information, provide a helpful response to the customer. If you cannot fully resolve the issue or if it requires human intervention, indicate that the ticket should be escalated.

Return your response as a valid JSON object with exactly the following parameters:
- "response": (str) A helpful and professional response to the customer's ticket
- "requires_escalation": (bool) Whether this ticket needs to be escalated to a human agent (true or false)

Ensure to write the JSON object in between these markers ```json and ```
"""

ESCALATION_JUSTIFIER_TEMPLATE = """You are a customer support supervisor. Your task is to provide a justification for why a ticket needs to be escalated to a human agent.

Ticket ID: {ticket_id}
Customer Name: {customer_name}
Ticket Content: {ticket_content}
Category: {category}
AI Response: {response}
Requires Escalation: {requires_escalation}

Since this ticket requires escalation, provide a clear and concise justification for why human intervention is necessary.

Return your response as a valid JSON object with exactly the following parameters:
- "escalation_reason": (str) A clear explanation of why this ticket needs human intervention

Ensure to write the JSON object in between these markers ```json and ```
"""