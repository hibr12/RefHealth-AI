from datetime import datetime, timezone
from corecare.integration import Chat, Document, assistant
d=Document(id="profile:test",hospital_id="test",category="profile",content="Felege Hiwot Comprehensive Specialized Hospital is in Bahir Dar, Ethiopia.",source="Hospital-maintained profile",updated_at=datetime.now(timezone.utc),review_at=None)
try:
    result=assistant(Chat(hospital_id="test",question="Which city is Felege Hiwot Comprehensive Specialized Hospital in? Answer from the approved directory.",documents=[d],history=[]))
    print("answer="+result["data"]["answer"])
    print("retrieval="+result["data"]["retrieval"])
    print("source_count="+str(len(result["data"]["sources"])))
except Exception as error:
    print("error_type="+type(error).__name__)
    print("error_detail="+str(getattr(error,"detail",str(error))))