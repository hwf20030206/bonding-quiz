import streamlit as st
import pandas as pd
import random
import glob
import json
import os
from datetime import datetime

st.set_page_config(page_title="键合题库 Pro Max", page_icon="📱", layout="centered")

# ==========================================
# 数据持久化辅助函数
# ==========================================
MISTAKES_FILE = "mistakes.json"
HISTORY_FILE = "history.json"

def load_json(filepath, default_val):
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default_val
    return default_val

def save_json(data, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==========================================
# UI 渲染辅助函数：高级追溯面板 (支持在首页复用)
# ==========================================
def render_traceback_records(records, reverse=False):
    recs = reversed(records) if reverse else records
    for rec in recs:
        icon = "✅" if rec['is_correct'] else "❌"
        st.markdown(f"**第 {rec['idx']} 题** {icon} ({rec['type']}) {rec['content']}")
        
        with st.expander("🔍 查看原题与作答明细"):
            # 兼容旧记录没有 source 或 knowledge 的情况
            source = rec.get('source', '未知文件')
            knowledge = rec.get('knowledge', '无')
            st.caption(f"**📁 题库来源**: `{source}` &nbsp;|&nbsp; **📚 知识点**: `{knowledge}`")
            
            for opt in rec['options']:
                opt_letter = opt[0]
                if opt_letter in rec['correct_ans'] and opt_letter in rec['user_ans']:
                    st.success(f"**{opt}** *(✅ 您的选择)*")
                elif opt_letter in rec['correct_ans']:
                    st.info(f"**{opt}** *(🎯 正确答案)*")
                elif opt_letter in rec['user_ans']:
                    st.error(f"**{opt}** *(❌ 您的错选)*")
                else:
                    st.markdown(f"<span style='color:gray;'>&nbsp;&nbsp;&nbsp;&nbsp;{opt}</span>", unsafe_allow_html=True)
            
            st.markdown("---")
            st.write(f"**💡 详细解析**：\n{rec['explanation']}")
        st.markdown("---")

# ==========================================
# 1. 加载核心题库数据
# ==========================================
@st.cache_data
def load_questions():
    questions = []
    files = [f for f in glob.glob("*.xlsx") if not f.startswith("~$")]
    if not files:
        return []
        
    for f in files:
        try:
            df = pd.read_excel(f)
            col_map = {
                '选项 A': '选项A', '选项 B': '选项B', '选项 C': '选项C', '选项 D': '选项D',
                '题干 ': '题干', '正确答案 ': '正确答案'
            }
            df.rename(columns=col_map, inplace=True)
            
            for _, row in df.iterrows():
                q_type = str(row.get('题型', ''))
                if any(t in q_type for t in ['单选', '多选', '判断']):
                    if pd.notna(row.get('题干')) and pd.notna(row.get('正确答案')):
                        options = [f"{k}. {row[f'选项{k}']}" for k in ['A','B','C','D'] if f'选项{k}' in df.columns and pd.notna(row.get(f'选项{k}'))]
                        ans = str(row['正确答案']).strip().upper().replace(" ", "")
                        
                        if '判断' in q_type and not options:
                            options = ["A. 正确", "B. 错误"]
                            if ans in ['对', '正确', '√', 'T', 'TRUE']: 
                                ans = 'A'
                            elif ans in ['错', '错误', '×', 'F', 'FALSE']: 
                                ans = 'B'
                        
                        if '多选' in q_type: type_label = '多选题'
                        elif '判断' in q_type: type_label = '判断题'
                        else: type_label = '单选题'
                        
                        q = {
                            'content': str(row['题干']).strip(),
                            'options': options,
                            'answer': ans,
                            'explanation': str(row.get('解析', '无解析')),
                            'knowledge': str(row.get('知识点', row.get('知识点分类', '无'))),
                            'type': type_label,
                            'source': f
                        }
                        questions.append(q)
        except Exception as e:
            st.error(f"读取文件出错：{e}")
    return questions

all_questions = load_questions()

# ==========================================
# 2. 初始化全局状态机
# ==========================================
if 'mistakes' not in st.session_state:
    raw_mistakes = load_json(MISTAKES_FILE, {})
    if isinstance(raw_mistakes, list):
        st.session_state.mistakes = {q: 2 for q in raw_mistakes}
        save_json(st.session_state.mistakes, MISTAKES_FILE)
    else:
        st.session_state.mistakes = raw_mistakes

if 'history' not in st.session_state:
    st.session_state.history = load_json(HISTORY_FILE, [])

if 'app_state' not in st.session_state:
    st.session_state.app_state = 'idle'  
    st.session_state.play_mode = ''      
    st.session_state.selected_q = []
    st.session_state.current_idx = 0
    st.session_state.score = 0
    st.session_state.answered = False
    st.session_state.is_correct = False
    st.session_state.round_id = 0 
    st.session_state.mistake_msg = "" 
    st.session_state.session_records = [] 

# ==========================================
# 侧边栏导航与控制
# ==========================================
st.sidebar.title("导航菜单")
menu_disabled = st.session_state.app_state == 'playing'
page = st.sidebar.radio(
    "请选择功能：", 
    ["🏠 首页与成绩", "🚀 随机测验", "📓 错题本专项复习"],
    disabled=menu_disabled
)

st.sidebar.divider()

if st.sidebar.button("🔄 强制重置当前进度"):
    st.session_state.app_state = 'idle'
    st.rerun()

if st.sidebar.button("📥 同步最新 Excel 题库", type="primary"):
    st.cache_data.clear()
    st.session_state.app_state = 'idle'
    st.rerun()

# ==========================================
# 页面一：首页与历史成绩 (新增：历史试卷追溯)
# ==========================================
if page == "🏠 首页与成绩" and st.session_state.app_state != 'playing':
    st.title("📱 键合题库学习中心")
    
    if not all_questions:
        st.error("⚠️ 未能加载到题库，请确保 '键合题库.xlsx' 文件与本程序在同一目录下！")
        st.stop()
        
    st.info(f"📚 当前题库共收录了 **{len(all_questions)}** 道题。您当前有 **{len(st.session_state.mistakes)}** 道错题待攻克。")
    
    st.subheader("📊 您的历史测验记录")
    if not st.session_state.history:
        st.write("暂无答题记录，快去开启一次测验吧！")
    else:
        # 显示图表和精简版表格 (剔除掉占用空间极大的'作答明细'列)
        history_df = pd.DataFrame(st.session_state.history)
        display_df = history_df.drop(columns=["作答明细"], errors='ignore')
        display_df = display_df.sort_values(by="日期", ascending=False).reset_index(drop=True)
        
        st.line_chart(display_df['正确率(%)'].rename("历次准确率趋势"))
        st.dataframe(display_df, use_container_width=True)
        
        # === 核心新增：历史测验试卷追溯 ===
        st.divider()
        st.subheader("🔍 历史测验试卷追溯")
        st.write("您可以随时在此处重新翻阅您过去的每一次测验内容与答对/答错明细。")
        
        # 将历史记录倒序排列，最新的在最上面
        reversed_history = list(reversed(st.session_state.history))
        # 制作下拉菜单选项标签
        record_options = {f"{r['日期']} | {r['模式']} | 得分: {r['得分']}/{r['题目数']}": r for r in reversed_history}
        
        selected_record_key = st.selectbox("👉 请选择要回顾的历史测验：", list(record_options.keys()))
        
        if selected_record_key:
            selected_rec = record_options[selected_record_key]
            details = selected_rec.get("作答明细", [])
            
            if not details:
                st.info("⚠️ 这是一条早期版本的记录，当时尚未上线作答明细保存功能，无法查看原题。")
            else:
                st.write(f"以下为您在 **{selected_rec['日期']}** 参加的 **{selected_rec['模式']}** 的完整试卷：")
                with st.container(border=True):
                    render_traceback_records(details, reverse=False)

# ==========================================
# 页面二/三的设置入口：测验准备
# ==========================================
elif st.session_state.app_state == 'idle':
    if not all_questions:
        st.error("⚠️ 题库为空，请检查文件或点击左侧同步按钮。")
        st.stop()
        
    if page == "🚀 随机测验":
        st.title("🚀 随机测验模式")
        default_q = min(20, len(all_questions))
        num_q = st.number_input("👉 请输入本次测验的题目数量：", min_value=1, max_value=len(all_questions), value=default_q, step=1)
        if st.button("开始测验", type="primary"):
            st.session_state.selected_q = random.sample(all_questions, num_q)
            st.session_state.play_mode = 'random'
            st.session_state.app_state = 'playing'
            st.session_state.current_idx = 0
            st.session_state.score = 0
            st.session_state.answered = False
            st.session_state.round_id += 1
            st.session_state.session_records = [] 
            st.rerun()
            
    elif page == "📓 错题本专项复习":
        st.title("📓 错题本专项复习")
        if not st.session_state.mistakes:
            st.success("🎉 太棒了！您的错题本是空的！")
            st.balloons()
        else:
            mistake_pool = [q for q in all_questions if q['content'] in st.session_state.mistakes]
            if not mistake_pool:
                st.warning("您之前的错题在最新的题库中找不到了，已自动清空无效错题。")
                st.session_state.mistakes = {}
                save_json({}, MISTAKES_FILE)
                st.stop()
                
            st.warning(f"⚠️ 错题本中目前有 **{len(mistake_pool)}** 道待攻克的题目。")
            st.write("💡 严格模式：**每道错题必须答对 2 次才能移除。如果在期间答错，要求次数将重置回 2 次！**")
            
            num_m = st.number_input("👉 打算复习多少道错题？", min_value=1, max_value=len(mistake_pool), value=len(mistake_pool), step=1)
            if st.button("开始攻克错题", type="primary"):
                st.session_state.selected_q = random.sample(mistake_pool, num_m)
                st.session_state.play_mode = 'mistake'
                st.session_state.app_state = 'playing'
                st.session_state.current_idx = 0
                st.session_state.score = 0
                st.session_state.answered = False
                st.session_state.round_id += 1
                st.session_state.session_records = [] 
                st.rerun()

# ==========================================
# 答题主循环 (playing 状态)
# ==========================================
elif st.session_state.app_state == 'playing':
    total_q = len(st.session_state.selected_q)
    q = st.session_state.selected_q[st.session_state.current_idx]
    is_multi = "多选" in q['type']
    
    st.progress(st.session_state.current_idx / total_q)
    st.caption(f"模式：{'🚀 随机测验' if st.session_state.play_mode=='random' else '📓 错题本复习'} | 第 {st.session_state.current_idx + 1} / {total_q} 题")
    
    type_color = "#1f77b4" if q['type'] == '单选题' else ("#ff7f0e" if q['type'] == '多选题' else "#2ca02c")
    st.markdown(f"### <span style='color:{type_color};'>【{q['type']}】</span> {q['content']}", unsafe_allow_html=True)
    st.write(f"*(知识点: {q['knowledge']})*")
    
    user_ans_list = []
    user_ans_single = None
    
    if is_multi:
        st.write("📌 *请选择所有符合题意的选项（漏选、错选均不得分）：*")
        for i, opt in enumerate(q['options']):
            cb_key = f"cb_{st.session_state.round_id}_{st.session_state.current_idx}_{i}"
            if st.checkbox(opt, disabled=st.session_state.answered, key=cb_key):
                user_ans_list.append(opt[0]) 
    else:
        user_ans_single = st.radio("请选择一个最佳答案：", q['options'], index=None, disabled=st.session_state.answered)
    
    if not st.session_state.answered:
        if st.button("提交答案", type="primary"):
            user_ans_str = ""
            if is_multi:
                if not user_ans_list:
                    st.warning("⚠️ 请至少选择一个答案")
                    st.stop()
                user_ans_str = "".join(sorted(user_ans_list))
            else:
                if not user_ans_single:
                    st.warning("⚠️ 请先选择一个答案")
                    st.stop()
                user_ans_str = user_ans_single[0]
                
            correct_ans_str = "".join(sorted(list(q['answer'])))
            
            st.session_state.answered = True
            st.session_state.user_ans_display = user_ans_str
            st.session_state.mistake_msg = "" 
            
            if user_ans_str == correct_ans_str:
                st.session_state.is_correct = True
                st.session_state.score += 1
                if st.session_state.play_mode == 'mistake' and q['content'] in st.session_state.mistakes:
                    st.session_state.mistakes[q['content']] -= 1
                    remain_times = st.session_state.mistakes[q['content']]
                    if remain_times <= 0:
                        del st.session_state.mistakes[q['content']]
                        st.session_state.mistake_msg = "🔥 完美掌握！这道题已彻底从错题本中移除。"
                    else:
                        st.session_state.mistake_msg = f"👍 答对了！但这道题还需要再答对 **{remain_times}** 次才能彻底移除哦。"
                    save_json(st.session_state.mistakes, MISTAKES_FILE)
            else:
                st.session_state.is_correct = False
                st.session_state.mistakes[q['content']] = 2
                save_json(st.session_state.mistakes, MISTAKES_FILE)
            
            st.session_state.session_records.append({
                'idx': st.session_state.current_idx + 1,
                'content': q['content'],
                'type': q['type'],
                'options': q['options'],
                'knowledge': q['knowledge'],
                'source': q['source'],
                'user_ans': user_ans_str,
                'correct_ans': correct_ans_str,
                'is_correct': st.session_state.is_correct,
                'explanation': q['explanation']
            })
            
            st.rerun()
                
    else:
        if st.session_state.is_correct:
            st.success("✅ 回答正确！")
            if st.session_state.play_mode == 'mistake' and st.session_state.mistake_msg:
                st.info(st.session_state.mistake_msg)
        else:
            st.error(f"❌ 错误！您的答案是: **{st.session_state.user_ans_display}**")
            st.warning("📥 记忆需要巩固！此题已在【错题本】中记录（要求连续答对 2 次）。")
        
        st.info(f"### 🎯 正确答案：{q['answer']}\n\n**💡 解析**：\n{q['explanation']}")
        
        if st.session_state.current_idx < total_q - 1:
            if st.button("下一题", type="primary"):
                st.session_state.current_idx += 1
                st.session_state.answered = False
                st.rerun()
        else:
            if st.button("📝 交卷并保存成绩", type="primary"):
                st.session_state.app_state = 'finished'
                st.rerun()

    st.divider()
    if st.session_state.session_records:
        with st.expander(f"👀 查看本次已作答记录 (已答 {len(st.session_state.session_records)} 题)"):
            render_traceback_records(st.session_state.session_records, reverse=True)

# ==========================================
# 测验结束状态 (finished 状态)
# ==========================================
elif st.session_state.app_state == 'finished':
    st.balloons()
    total_q = len(st.session_state.selected_q)
    accuracy = round((st.session_state.score / total_q) * 100, 1)
    
    # 【新增】：交卷时，将整张卷子的作答明细（session_records）打包存入这笔历史记录中
    record = {
        "日期": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "模式": "随机测验" if st.session_state.play_mode == 'random' else "错题复习",
        "题目数": total_q,
        "得分": st.session_state.score,
        "正确率(%)": accuracy,
        "作答明细": st.session_state.session_records
    }
    st.session_state.history.append(record)
    save_json(st.session_state.history, HISTORY_FILE)
    
    st.success("🎉 恭喜您完成了本次测验！试卷与成绩已成功归档入库。")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("测验模式", record["模式"])
    col2.metric("得分/总题数", f"{st.session_state.score} / {total_q}")
    col3.metric("正确率", f"{accuracy}%")
    
    if st.button("🔙 返回主页查看历史试卷", type="primary"):
        st.session_state.app_state = 'idle'
        st.rerun()

    st.divider()
    if st.session_state.session_records:
        st.subheader("📝 本次答卷全记录与原题深度追溯")
        render_traceback_records(st.session_state.session_records, reverse=False)