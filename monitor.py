Run python monitor.py
Traceback (most recent call last):
  File "/home/runner/work/celebritycruises/celebritycruises/monitor.py", line 120, in <module>
正在載入名人郵輪網頁...
載入或等待元素時發生錯誤: Page.wait_for_selector: Timeout 30000ms exceeded.
Call log:
  - waiting for locator("div[data-testid^='cruise-card-']") to be visible

正在擷取畫面與 HTML 原始碼以供除錯...
    parse_cruises()
  File "/home/runner/work/celebritycruises/celebritycruises/monitor.py", line 64, in parse_cruises
    raise e # 再次拋出錯誤讓 Actions 標示為失敗
  File "/home/runner/work/celebritycruises/celebritycruises/monitor.py", line 55, in parse_cruises
    page.wait_for_selector("div[data-testid^='cruise-card-']", timeout=30000)
  File "/opt/hostedtoolcache/Python/3.10.20/x64/lib/python3.10/site-packages/playwright/sync_api/_generated.py", line 8928, in wait_for_selector
    self._sync(
  File "/opt/hostedtoolcache/Python/3.10.20/x64/lib/python3.10/site-packages/playwright/_impl/_sync_base.py", line 115, in _sync
    return task.result()
  File "/opt/hostedtoolcache/Python/3.10.20/x64/lib/python3.10/site-packages/playwright/_impl/_page.py", line 427, in wait_for_selector
    return await self._main_frame.wait_for_selector(**locals_to_params(locals()))
  File "/opt/hostedtoolcache/Python/3.10.20/x64/lib/python3.10/site-packages/playwright/_impl/_frame.py", line 394, in wait_for_selector
    await self._channel.send(
  File "/opt/hostedtoolcache/Python/3.10.20/x64/lib/python3.10/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
  File "/opt/hostedtoolcache/Python/3.10.20/x64/lib/python3.10/site-packages/playwright/_impl/_connection.py", line 563, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
playwright._impl._errors.TimeoutError: Page.wait_for_selector: Timeout 30000ms exceeded.
Call log:
  - waiting for locator("div[data-testid^='cruise-card-']") to be visible

Error: Process completed with exit code 1.
