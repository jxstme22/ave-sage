"""Direct test of the collector REST polling to see what AVE returns."""
import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.collector import CollectorOrchestrator, SignificanceScorer, AveRestCollector
from config import settings

async def main():
    scorer = SignificanceScorer(settings.collection.__dict__)
    print(f"Significance threshold: {scorer.threshold}")
    
    rest = AveRestCollector(settings.ave.api_key, settings.ave.chains, scorer)
    async with rest:
        for chain in settings.ave.chains:
            print(f"\n=== Polling {chain} ===")
            
            # Get trending
            trending = await rest.get_trending(chain)
            print(f"  Trending events: {len(trending)}")
            for t in trending[:5]:
                print(f"    {t.token_symbol} sig={t.significance:.2f} data={t.data}")
            
            if trending:
                # Try price/risk for first token
                first = trending[0]
                print(f"\n  --- Deep dive: {first.token_symbol} ---")
                price = await rest.get_price_and_risk(chain, first.token, first.token_symbol)
                if price:
                    print(f"  Price event: sig={price.significance:.2f} data={price.data}")
                else:
                    print(f"  Price event: None (not significant)")
                    
                klines = await rest.get_klines(chain, first.token, first.token_symbol)
                print(f"  Kline events: {len(klines)}")
                for k in klines:
                    print(f"    vol_mult={k.data.get('volume_multiplier',0):.1f} sig={k.significance:.2f}")
                    
                swaps = await rest.get_large_swaps(chain, first.token, first.token_symbol)
                print(f"  Large swap events: {len(swaps)}")
                for s in swaps[:3]:
                    print(f"    ${s.data.get('amount_usd',0):,.0f} sig={s.significance:.2f}")

asyncio.run(main())
