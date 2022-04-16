# -*-coding:utf-8-*-
import math
import os
import django
import operator
import numpy as np
from course.models import *


os.environ["DJANGO_SETTINGS_MODULE"] = "course_master.settings"
django.setup()


class UserCf:
    # 基于用户协同算法来获取推荐列表
    """
    利用用户的群体行为来计算用户的相关性。
    计算用户相关性的时候我们就是通过对比他们选修过多少相同的课程相关度来计算的
    举例：
    --------+--------+--------+--------+--------+
            |   X    |    Y   |    Z   |    R   |
    --------+--------+--------+--------+--------+
        a   |   1    |    1   |    1   |    0   |
    --------+--------+--------+--------+--------+
        b   |   1    |    0   |    1   |    0   |
    --------+--------+--------+--------+--------+
        c   |   1    |    1   |    0   |    1   |
    --------+--------+--------+--------+--------+

    a用户选修了：X、Y、Z
    b用户选修了：X、Z
    c用户选修了：X、Y、R

    那么很容易看到a用户和b、c用户非常相似，给a用户推荐课程R，
    给b用户推荐课程Y
    给c用户推荐课程Z
    这就是基于用户的协同过滤。
    a用户向量为(1,1,1,0)
    b用户向量为(1,0,1,0)
    c用户向量为(1,1,0,1)
    找a用户的相似用户，则计算a向量与其他向量的夹角即可，夹角越小则说明越相近
    利用求高维空间向量的夹角,可以估计两组数据的吻合程度
    """

    # 获得初始化数据
    def __init__(self, data):
        self.data = data

    # 计算N维向量的夹角
    def calc_vector_cos(self, a, b):
        '''
        cos=(ab的内积)/(|a||b|)
        :param a: 向量a
        :param b: 向量b
        :return: 夹角值
        '''
        a_n = np.array(a)
        b_n = np.array(b)
        if any(b_n) == 0:
            return 0
        cos_ab = a_n.dot(b_n) / (np.linalg.norm(a_n) * np.linalg.norm(b_n))
        return round(cos_ab, 2)


    # 计算与当前用户的距离，获得最临近的用户
    def nearest_user(self, username, n=1):
        distances = {}
        # 用户，相似度
        # 遍历整个数据集
        for user, rate_set in self.data.items():
            # 非当前的用户
            if user != username:
                vector_a = tuple(self.data[username].values())
                vector_b = tuple(self.data[user].values())
                distance = self.calc_vector_cos(vector_a, vector_b)
                # 计算两个用户的相似度
                distances[user] = distance
        # 排序，按向量夹角由小到到排序
        closest_distance = sorted(distances.items(), key=operator.itemgetter(1), reverse=True)
        # 最相似的N个用户
        # print("closest user:", closest_distance[:n])
        return closest_distance[:n]

    # 给用户推荐课程
    def recommend(self, username, n=1):
        recommend = set()
        nearest_user = self.nearest_user(username, n) # 获取最相近的n个用户
        for user_id, _ in nearest_user:
            for usercourse in UserCourse.objects.filter(user_id=user_id):
                if usercourse.course.id not in self.data[username].keys():
                    recommend.add(usercourse.course.id)
        return recommend

def recommend_by_user_id(user_id):
    # 通过用户协同算法来进行推荐
    current_user = User.objects.get(id=user_id)
    # 如果当前用户没有选修过课程，则按照收藏量降序返回
    if current_user.usercourse_set.count() == 0:
        courses = CourseInfo.objects.all().order_by('-collect_num')
        if courses.count() > 30:
            courses = courses[:30]
        return courses
    data = {}
    course_ids = []
    other_user_ids = set()
    # 把该用户选修过的课程变成向量字典：{'用户id': {'课程1id': 1, '课程2id': 1...}}
    for u_course in current_user.usercourse_set.all():
        # 遍历用户选修过的课程
        if not data:
            data[current_user.id] = {u_course.course.id: 1}  # 已选课程，设置值为1
        else:
            data[current_user.id][u_course.course.id] = 1
        course_ids.append(u_course.course)
        # 获取其他选修过该课程的用户id
        for usercourse in UserCourse.objects.filter(course=u_course.course):
            if usercourse.user.id != current_user.id:
                other_user_ids.add(usercourse.user.id)

    # 把选修过其中课程的用户选修过的课程变成向量字典：{'用户2id': {'课程1id': 0, '课程2id': 1...}}
    for other_user in User.objects.filter(pk__in=other_user_ids):
        other_user_id = other_user.id
        for i in range(len(course_ids)):
            course = course_ids[i]
            if UserCourse.objects.filter(user_id=other_user_id, course=course):
                is_select = 1
            else:
                is_select = 0
            if other_user_id not in data:
                data[other_user_id] = {course.id: is_select}  # 已选课程，设置值为1,未选课程设置为0
            else:
                data[other_user_id][course.id] = is_select

    user_cf = UserCf(data=data)
    recommend_ids = user_cf.recommend(current_user.id, 1)

    if not recommend_ids:
        # 如果没有找到相似用户则按照收藏量降序返回
        courses = CourseInfo.objects.all().order_by('-collect_num')
        if courses.count() > 30:
            courses = courses[:30]
        return courses

    return CourseInfo.objects.filter(id__in=recommend_ids).order_by('-select_num')
