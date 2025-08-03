"""
Random Service
"""

import aiohttp
import random
import logging

logger = logging.getLogger(__name__)

class RandomService:
    
    
    @staticmethod
    async def get_true_random_choice(options: list):
        
        try:
            async with aiohttp.ClientSession() as session:
                
                url = f"https://www.random.org/integers/?num=1&min=0&max={len(options)-1}&col=1&base=10&format=plain&rnd=new"
                
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        random_index = int(await response.text())
                        logger.info(f"✅ True Random from random.org: Index {random_index} -> {options[random_index]}")
                        return options[random_index]
                    else:
                        logger.warning(f"❌ random.org error: Status {response.status}")
                        return random.choice(options)
        except Exception as e:
            logger.warning(f"❌ random.org not reachable: {e}")
            logger.info("🔄 Fallback to local random generator")
            return random.choice(options)
    
    @staticmethod
    async def get_true_random_numbers(count: int, min_val: int, max_val: int) -> list:
        
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://www.random.org/integers/?num={count}&min={min_val}&max={max_val}&col=1&base=10&format=plain&rnd=new"
                
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        numbers_text = await response.text()
                        numbers = [int(line.strip()) for line in numbers_text.strip().split('\n')]
                        logger.info(f"✅ True Random numbers from random.org: {numbers}")
                        return numbers
                    else:
                        logger.warning(f"❌ random.org error for numbers: Status {response.status}")
                        return [random.randint(min_val, max_val) for _ in range(count)]
        except Exception as e:
            logger.warning(f"❌ random.org not reachable for numbers: {e}")
            return [random.randint(min_val, max_val) for _ in range(count)]