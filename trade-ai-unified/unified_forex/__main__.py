"""Source-checkout launcher. Public network hosting is outside this delivery."""
import uvicorn
if __name__=='__main__':
    uvicorn.run('unified_forex.api:app',host='127.0.0.1',port=8006,workers=1)
