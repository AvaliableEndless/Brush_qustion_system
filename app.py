from flask import Flask, render_template, request, jsonify
from docx import Document
import os
import random
import re

app = Flask(__name__)

# 存储题目数据
questions = []
used_questions = set()  # 用于记录已使用的题目索引
question_history = []  # 用于记录题目历史
question_sequence = {}  # 用于记录题目序号映射
current_sequence = 0  # 当前题目序号

def is_question_number(text):
    """判断是否是题目序号"""
    return bool(re.match(r'^\d+\.', text))

def load_questions(file_path):
    global questions, used_questions, question_history, question_sequence, current_sequence
    questions = []
    used_questions.clear()
    question_history.clear()
    question_sequence.clear()
    current_sequence = 0
    try:
        doc = Document(file_path)
        current_question = None
        current_options = []
        current_answer = None
        current_type = None
        
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue
            
            # 检查段落是否加粗
            is_bold = False
            for run in paragraph.runs:
                if run.bold:
                    is_bold = True
                    break
            
            if is_bold:
                # 如果已经有题目，保存之前的题目
                if current_question:
                    questions.append({
                        'question': current_question,
                        'options': current_options,
                        'answer': current_answer,
                        'type': current_type
                    })
                # 设置新的题型
                current_type = text
                current_question = None
                current_options = []
                current_answer = None
            elif is_question_number(text):
                # 如果已经有题目，保存之前的题目
                if current_question:
                    questions.append({
                        'question': current_question,
                        'options': current_options,
                        'answer': current_answer,
                        'type': current_type
                    })
                # 开始新题目
                current_question = text
                current_options = []
                current_answer = None
            elif text.startswith(('A.', 'B.', 'C.', 'D.', 'E.')):
                current_options.append(text)
            elif text.startswith('答案：'):
                current_answer = text.replace('答案：', '').strip()
        
        # 保存最后一道题目
        if current_question:
            questions.append({
                'question': current_question,
                'options': current_options,
                'answer': current_answer,
                'type': current_type
            })
        
        return True, f"成功加载 {len(questions)} 道题目"
    except Exception as e:
        return False, f"加载文件时出错：{str(e)}"

def get_random_question():
    """获取一个未使用过的随机题目"""
    global current_sequence
    available_questions = [i for i in range(len(questions)) if i not in used_questions]
    if not available_questions:
        # 如果所有题目都已使用，重置使用记录
        used_questions.clear()
        available_questions = list(range(len(questions)))
    
    question_index = random.choice(available_questions)
    used_questions.add(question_index)
    
    # 增加序号并记录映射
    current_sequence += 1
    question_sequence[current_sequence] = question_index
    question_history.append(current_sequence)
    
    return current_sequence, questions[question_index]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有选择文件'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '没有选择文件'})
    
    if not file.filename.endswith('.docx'):
        return jsonify({'success': False, 'message': '请选择Word文档(.docx)文件'})
    
    # 保存文件
    file_path = os.path.join('uploads', file.filename)
    os.makedirs('uploads', exist_ok=True)
    file.save(file_path)
    
    # 加载题目
    success, message = load_questions(file_path)
    
    # 删除临时文件
    try:
        os.remove(file_path)
    except:
        pass
    
    if success:
        # 获取随机题目
        sequence_number, question = get_random_question()
        return jsonify({
            'success': True,
            'message': message,
            'question': question,
            'sequence_number': sequence_number
        })
    else:
        return jsonify({'success': False, 'message': message})

@app.route('/check_answer', methods=['POST'])
def check_answer():
    data = request.get_json()
    sequence_number = data.get('sequence_number', 0)
    selected_answer = data.get('answer')
    
    if sequence_number not in question_sequence:
        return jsonify({'success': False, 'message': '题目不存在'})
    
    question_index = question_sequence[sequence_number]
    question = questions[question_index]
    is_correct = False
    
    # 根据题型判断答案
    if question['type'] == '多选题':
        # 多选题答案需要完全匹配
        correct_answers = set(question['answer'])
        selected_answers = set(selected_answer)
        is_correct = correct_answers == selected_answers
    elif question['type'] == '填空题':
        # 填空题答案不区分大小写，忽略空格
        correct_answers = [ans.strip().lower() for ans in question['answer'].split('，')]
        selected_answers = [ans.strip().lower() for ans in selected_answer.split('，')]
        is_correct = correct_answers == selected_answers
    elif question['type'] == '判断题':
        # 判断题答案需要完全匹配
        is_correct = selected_answer == question['answer']
    else:
        # 单选题
        is_correct = selected_answer == question['answer']
    
    return jsonify({
        'success': True,
        'is_correct': is_correct,
        'correct_answer': question['answer'],
        'type': question['type']
    })

@app.route('/get_answer', methods=['POST'])
def get_answer():
    data = request.get_json()
    sequence_number = data.get('sequence_number', 0)
    
    if sequence_number not in question_sequence:
        return jsonify({'success': False, 'message': '题目不存在'})
    
    question_index = question_sequence[sequence_number]
    question = questions[question_index]
    return jsonify({
        'success': True,
        'answer': question['answer'],
        'type': question['type']
    })

@app.route('/next_question', methods=['POST'])
def next_question():
    data = request.get_json()
    current_sequence = data.get('sequence_number', 0)
    
    # 获取当前题目在历史记录中的位置
    current_history_index = question_history.index(current_sequence) if current_sequence in question_history else -1
    
    # 如果当前题目不是历史记录中的最后一题，返回下一题
    if current_history_index >= 0 and current_history_index < len(question_history) - 1:
        next_sequence = question_history[current_history_index + 1]
        question_index = question_sequence[next_sequence]
        return jsonify({
            'success': True,
            'question': questions[question_index],
            'sequence_number': next_sequence
        })
    else:
        # 如果是最后一题，获取新的随机题目
        sequence_number, question = get_random_question()
        return jsonify({
            'success': True,
            'question': question,
            'sequence_number': sequence_number
        })

@app.route('/previous_question', methods=['POST'])
def previous_question():
    data = request.get_json()
    current_sequence = data.get('sequence_number', 0)
    
    # 从历史记录中获取上一题
    if len(question_history) > 1:
        # 获取当前题目在历史记录中的位置
        current_history_index = question_history.index(current_sequence) if current_sequence in question_history else -1
        
        if current_history_index > 0:
            # 获取上一题
            prev_sequence = question_history[current_history_index - 1]
            question_index = question_sequence[prev_sequence]
            return jsonify({
                'success': True,
                'question': questions[question_index],
                'sequence_number': prev_sequence
            })
    
    # 如果没有历史记录或当前题目不在历史记录中，返回当前题目
    question_index = question_sequence[current_sequence]
    return jsonify({
        'success': True,
        'question': questions[question_index],
        'sequence_number': current_sequence
    })

if __name__ == '__main__':
    app.run(debug=True) 