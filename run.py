from main import app, config, init
import asyncio
tasks = [
    app.run_task(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG
    ),
    # init()
    ]
asyncio.get_event_loop().run_until_complete(
    asyncio.ensure_future(
        asyncio.gather(*tasks)
    )
)
