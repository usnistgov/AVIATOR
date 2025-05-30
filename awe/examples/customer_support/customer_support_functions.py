from datetime import datetime

def check_escalation(args):
    """
    Determines the next agent based on whether the ticket requires escalation.
    
    Args:
        args: The output from the TimestampAdder agent
        
    Returns:
        str: The name of the next agent to execute
    """
    if args.requires_escalation:
        return "EscalationJustifier"
    else:
        return "end" # End the workflow

def get_timestamp():
    """
    Adds a timestamp to the ticket response.
    
    Args:
        args: The input arguments containing ticket information
        
    Returns:
        dict: A dictionary with the final output including the timestamp
    """
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create the output dictionary
    output = {
        "timestamp": current_time
    }
        
    return output