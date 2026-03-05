"""
Script to fix corrupted plans data in the database
This will convert string "[]" to proper empty array []
"""
import os
import django
import sys

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_4_django.settings')
django.setup()

from org_domain.gym.mongo import org_gym_collection
import json

def fix_plans():
    """Fix all gyms with corrupted plans data"""
    
    # Find all gyms
    gyms = org_gym_collection.find({})
    
    fixed_count = 0
    for gym in gyms:
        gym_id = gym['_id']
        plans = gym.get('plans', [])
        
        print(f"\nGym: {gym.get('gym_name', 'Unknown')}")
        print(f"  Current plans: {plans}")
        print(f"  Plans type: {type(plans)}")
        
        needs_fix = False
        new_plans = []
        
        # Check if plans is a string
        if isinstance(plans, str):
            print(f"  -> Plans is a string, parsing...")
            try:
                new_plans = json.loads(plans)
                needs_fix = True
            except:
                print(f"  -> Failed to parse, setting to empty array")
                new_plans = []
                needs_fix = True
        
        # Check if plans is a list with string elements
        elif isinstance(plans, list) and len(plans) > 0:
            if isinstance(plans[0], str):
                print(f"  -> Plans contains string elements, parsing...")
                try:
                    new_plans = json.loads(plans[0])
                    needs_fix = True
                except:
                    print(f"  -> Failed to parse, setting to empty array")
                    new_plans = []
                    needs_fix = True
            else:
                print(f"  -> Plans looks OK")
                new_plans = plans
        else:
            print(f"  -> Plans is already correct")
            new_plans = plans if isinstance(plans, list) else []
        
        if needs_fix:
            print(f"  -> Updating to: {new_plans}")
            org_gym_collection.update_one(
                {'_id': gym_id},
                {'$set': {'plans': new_plans}}
            )
            fixed_count += 1
            print(f"  -> Fixed!")
    
    print(f"\n✅ Fixed {fixed_count} gym(s)")

if __name__ == '__main__':
    print("Starting plans fix script...")
    fix_plans()
    print("\nDone!")
