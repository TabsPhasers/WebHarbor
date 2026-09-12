# NVIDIA 确定性判分（repair001）

本目录沿用 @DEM1TASSE 的20个入口名，由 reviewer 修复判分实现；站点原贡献归属 @KaKituken。判分仅使用 Python 标准库，不 import Flask/app，不调用模型、网络、Docker 或其他进程，不读取默认实例DB。

## 调用与输出

```bash
python3 -B sites/nvidia/verify/verify_0.py \
  --run_dir /absolute/phase-input \
  --initial_db /absolute/phase-input/initial.db \
  --after_db /absolute/phase-input/after.db
```

`run_dir`必须包含本题完整`task.json`和`trajectory.json`；两DB必须显式提供。旧`--container`、`--no_llm`选项已移除，默认就是确定性判分。

- task.json逐字段等于本源码同站点`tasks.jsonl`中的本题定义，ID与当前入口一致。部署staging若有显式路径转换，必须同步其本地canonical tasks与传入task；不能偷偷接受旧题/旧rubric。
- trajectory采用当前native-ready runtime格式：`task_id`、准确`query`、`steps`数组、字符串`final_answer`；每步连续整数`step`及`url`/`url_before`/`url_after`。可选`final_url`、`boundary_events`也参与判定。无动作baseline为`steps=[]`、空答案；T11正常终态必须有`final_url`。
- URL按实际origin和精确path/query解析；端口可按运行映射变化，不强制任务文件的40023。相关对象证据来自真正对应的详情、含目标slug的comparison、含目标行的driver结果或news列表；`?q=/products/...`不是详情页证据。
- 当前单站backend仅支持local loopback origin；跨origin/boundary事件导致FAIL。输入缺失/不可读/非法JSON（含重复键）、ID/query/task不符、schema/integrity/FK错误为INFRA。
- SQLite强制`mode=ro`和`query_only`，要求原应用完整10表/列与一致before/after schema。不会创建缺失DB，不会fallback到其他容器/题目。

stdout始终是一份JSON：`task_id`为本题、`pass`为严格bool、`reason`为说明、`evidence`为检查摘要。

|exit|语义|
|---|---|
|0|正常PASS，`pass=true`|
|1|正常任务FAIL，`pass=false`|
|2|INFRA_ERROR，`pass=false,error="INFRA_ERROR"`；外层应`success=false`，不能算正常负例|

此接口与native-ready `backend.verify()`的四输入复制/三个CLI参数一致；不依赖其未传输的截图目录或旧agent_demo的`step_*.png`命名。
比较页同时支持最终UI的原生GET `product=a&product=b`与旧`ids=a,b`；按app实际优先级前者覆盖后者，不能合并两组参数虚构已显示的产品。

## 判定原则

- 信息题：事实取显式initial DB（T11静态技术/购买事实见来源），必需相关页/对象证据。信息匹配使用型号实体、数值和单位、比较主语方向、版本分量与完整日期；不是substring。支持大小写/空白/千分位、GB/GDDR 7、USD/美元、W/watts等合理格式，以及清晰的日期格式。
- 确定性解析支持简洁事实句和明确关系，不保证理解任意修辞/暗示。遇歧义或矛盾返回FAIL，保持原输出并交独立主审；不调用LLM兜底，也不让LLM缺配置变成任务FAIL。
- T6题意指定comparison工具，必须同一比较包含5090/4090；T7未指定工具，可分别读两详情。T18相关news/search列表显示日期时可接受，不强制详情。T11必须技术页与5080购买页两类证据，最终停本地购买页，无固定浏览顺序。
- 状态题：DB是完成结果的权威依据，不附加英文最终回答或登录页面访问要求。按新增/删除row ID绑定同一账号和目标，保护所有其他wishlist/users/reviews/orders等记录。仅模拟driver download计数非递减作为无害副作用允许；不把账号/收藏误操作或额外订单当无害。
- Wishlist新增要求目标原先不存在、只新增一条；T16仅删Alice目标且保留所有其他条目。T14仅改Alice country，保留其他字段。T15同一新增row满足Alice/Jetson/5星/精确归一化标题/非空body；`Not Incredible`失败。T19仅新增指定邮箱subscription。
- T16历史校正：原版真实登录→account→详情移除路线本来会被原verifier接受；本修复不以简化URL fixture夸大原实际UI失败，改为直接按准确state判定。

## 任务变更与事实来源

20个源ID保留。仅T5/T11/T12/T17修改query语义，其余16题原query保留；全20题URL更新40023、rubric更新为英文FACT CHECKPOINTS。rubric只供grader，actor只接收ques，不得暴露此目录或rubric。

- T5：Orin Nano Super **8GB developer kit** 对比 Orin NX **16GB production module**；两个对象的内存与身份必须关联正确。保留正常商品价签，不靠删除可见价格制造难度。
- T11：Blackwell、第五代Tensor、第四代RT；RTX5080 **NVIDIA Marketplace / United States（en-us）**购买信息，停在本地，无外部访问/下单。
- T12：原40系列最低价卡转为Alice本地Wishlist。
- T17：镜像冻结价格、Gaming≥16GB最低价、具体RTX5060Ti **16GB版本**转为Alice本地Wishlist；不是实时零售价结论。

T11来源：官方`https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/`，2026-09-09离线采集。原HTML SHA256 `977dc25fd5586343e1e939bb67cae371a58b1d1df0e5d45c552eb7d55709c2fe`。可见文本含“NVIDIA Blackwell Architecture / Fifth-Gen Tensor Cores / Fourth-Gen Ray Tracing Cores”；该页5080“See All Buying Options”href为`https://marketplace.nvidia.com/en-us/consumer/graphics-cards/?...gpu=RTX%205080...`。来源只支撑入口与地区，不证明库存/价格/checkout。私有采集receipt、原始HTML及参考hash保存在review报告区，不随站点源码交付。

## 机械回归

使用正式素材或指定完整schema seed的**独立副本**，不import站点，输出必须是候选源树之外的新目录：

```bash
python3 -B sites/nvidia/tests/test_verifiers.py \
  --seed /absolute/nvidia/instance_seed/nvidia.db \
  --out /absolute/new-review-evidence-directory
```

覆盖每题no-op/正确fixture/专属near-miss，以及错账号/目标/delta、副作用、合法替代导航、格式正例和schema/身份INFRA。逐例保存输入DB/task/trajectory/hash、SQL变更、命令、stdout/stderr/exit与输入不变校验。fixture为机械证据，不是UI或native成绩；真实candidate seed、UI/native与独立主审仍需另行验收。
