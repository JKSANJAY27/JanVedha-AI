"""Simulate the full API call flow to find the 500 error."""
import sys, asyncio
sys.path.insert(0, '.')

# Simulate what the /query endpoint does step by step
async def test_api_flow():
    print("Step 1: Get advisor...")
    from app.services.rag.scheme_advisor import get_scheme_advisor
    advisor = get_scheme_advisor()
    print("✅ Advisor obtained")

    print("\nStep 2: Get langfuse trace_id...")
    try:
        from langfuse import get_client
        trace_id = get_client().get_current_trace_id()
        print(f"✅ Trace ID: {trace_id}")
    except Exception as e:
        trace_id = None
        print(f"⚠️  Langfuse error (non-fatal): {e}")

    print("\nStep 3: Run assess_eligibility...")
    try:
        result = advisor.assess_eligibility(
            profile_text="62 year old widow BPL family SC category income 2000 per month",
            ward_context="Ward 1"
        )
        print(f"✅ Result keys: {list(result.keys())}")
        if "error" in result:
            print(f"❌ Result contains 'error' key: {result['error']}")
        else:
            print(f"✅ eligible_schemes count: {len(result.get('eligible_schemes', []))}")
    except Exception as e:
        print(f"❌ assess_eligibility RAISED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\nStep 4: Simulate MongoDB record insert (without actual DB)...")
    from app.mongodb.models.scheme_query import SchemeQueryMongo
    record = SchemeQueryMongo(
        constituent_profile="test", 
        ward_id=1,
        councillor_user_id="test_user_id",
        result=result,
        langfuse_trace_id=trace_id
    )
    print(f"✅ Record created: {record.model_fields_set}")
    print("\n✅ All steps passed — the pipeline should work in the full API context")

asyncio.run(test_api_flow())
