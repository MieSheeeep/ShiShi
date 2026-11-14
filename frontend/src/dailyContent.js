import { newId } from './recipeEditing.js'
import { solarTermOf } from './solarTerms.js'
import { SOLAR_DIARIES } from './solarDiaries.js'

export function shanghaiDate(now=new Date()) {
  const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now)
  const part=type=>parts.find(p=>p.type===type).value
  return `${part('year')}-${part('month')}-${part('day')}`
}
export const publishedEditions=(rows,today)=>rows.filter(e=>e.date<=today).sort((a,b)=>b.date.localeCompare(a.date))
export const selectEdition=(rows,today)=>publishedEditions(rows,today)[0]||null

// 首页节气日记按当天所属节气取，与精选期次解耦。
export function diaryFor(date) {
  const {name}=solarTermOf(date)
  const entry=SOLAR_DIARIES[name]
  return entry?{...entry,term:name,date}:null
}

const winterDiary=(title,text)=>({term:'立冬',title,text,
  background:'立冬是冬季的第一个节气。节气记下时序，各地的冷暖仍有差异。',
  reference:{title:'节气背景：中国天气网 · 立冬',url:'https://e.weather.com.cn/mtqzt/4849618.shtml'}})

export const editions=[
  {
    date:'2026-11-10',issue:'003',name:'南瓜小米粥',emoji:'🥣',theme:'初冬 · 家常早餐',
    diary:winterDiary('天渐寒，晨粥正暖','清晨的厨房，从一锅小米粥开始醒来。南瓜在水里慢慢煮软，木勺搅过，留下淡淡的谷香。把早餐端上桌，也把一天的脚步放缓一点。'),
    headline:'把清晨，煮得暖一点。',intro:'一把小米，一块南瓜。用一锅慢煮的金黄，开始平常的一天。',
    reason:'南瓜切成小块，与小米同锅慢煮。食材简单，留一点时间给早餐，也留一点从容给自己。',
    image:'/editorial/pumpkin-millet.png',imageAlt:'陶碗中的南瓜小米粥，旁边放着木勺',
    minutes:'35',servings:'2人份',tools:'煮锅',tags:['早餐','慢煮'],
    ingredients:[['小米','100克'],['南瓜','200克'],['水','1000毫升']],
    steps:['小米淘洗干净；南瓜去皮去籽，切成约 1 厘米的小块。','锅中加水煮开，放入小米和南瓜，再次煮开后转小火。','小火煮约 25—30 分钟，间或搅拌，煮至小米软熟、南瓜绵软。可按喜好加水调整稀稠。'],
    pairing:'可搭配一个水煮蛋和一份蔬菜。粥是这一餐的一部分，按用餐人数与食量调整份量。',
    cultureTitle:'一碗粥里的地方日常',culture:'大同的地方饮食介绍里，小米可以煮粥，也可以与其他食材同焖。寻常谷物在不同厨房里，有不同的吃法。今天让南瓜的甜与小米的香，在一锅清水里慢慢相遇。',
    references:[{title:'云州区人民政府 · 小米粥',url:'https://www.yunzhou.gov.cn/yzqrmzfz/sqglmzzj/202011/f97762bc71174127a64035742b2db3d4.shtml'}]
  },
  {
    date:'2026-11-09',issue:'002',name:'香菇白菜炖豆腐',emoji:'🍲',theme:'初冬 · 一锅家常',
    diary:winterDiary('把初冬，炖进日常','天色收得早，晚饭也想做得暖一些。白菜、香菇和豆腐在锅里相聚，等一阵热气升起，厨房就有了家的气息。寻常的一锅，值得慢慢吃。'),
    headline:'一锅热气，就是晚饭。',intro:'白菜的清甜、香菇的鲜香，都留在这一锅里。',
    reason:'白菜、鲜香菇与豆腐同锅炖煮，材料容易准备。忙碌的工作日，可以把操作交给小火慢炖。',
    minutes:'25',servings:'2人份',tools:'炖锅',tags:['家常菜','炖煮'],
    ingredients:[['大白菜','300克'],['北豆腐','250克'],['鲜香菇','5朵'],['姜','2片'],['水','500毫升'],['油','1茶匙'],['盐','按口味少量添加']],
    steps:['白菜洗净切段，菜帮与菜叶分开放；豆腐切块，香菇洗净切片。','锅中放油和姜片，加入白菜帮与香菇略炒，倒入水。','煮开后放入豆腐，小火炖约 10 分钟；加入白菜叶再煮约 5 分钟，确认食材熟透，少量加盐调味。'],
    pairing:'搭配一小碗米饭或杂粮饭。采购时可以把剩余白菜留作下一餐，用量按实际人数调整。',
    cultureTitle:'顺着时令安排生活',culture:'二十四节气记录时令、气候与物候变化，也与各地的生活实践相连。同一个时令，不同地方有各自的餐桌。今天用一锅家常炖菜，记下初冬的一顿晚饭。',
    references:[{title:'中国非物质文化遗产网 · 二十四节气专题',url:'https://www.ihchina.cn/solar_terms.html'}]
  },
  {
    date:'2026-11-08',issue:'001',name:'番茄鸡蛋汤面',emoji:'🍜',theme:'初冬 · 一人食',
    diary:winterDiary('一碗热面，记下冬的开篇','立冬之后，给自己留一碗热面的时间。番茄煮出汤色，青菜添上一抹绿。不必等人齐，也不必等周末，一个人的晚饭同样值得认真。'),
    headline:'一个人，也认真开饭。',intro:'番茄炒出汁，鸡蛋煎出香。把寻常食材，做成一碗热面。',
    reason:'一份面、一枚鸡蛋，加上番茄和青菜。把几种食材安排在同一锅里，收拾起来也轻松。',
    minutes:'20',servings:'1人份',tools:'煮锅',tags:['一人食','面食'],
    ingredients:[['面条','80克'],['番茄','1个'],['鸡蛋','1个'],['小青菜','100克'],['水','600毫升'],['油','1茶匙'],['盐','按口味少量添加']],
    steps:['番茄洗净切块，青菜洗净；鸡蛋打散。','锅中放油，将蛋液炒至完全凝固后盛出；加入番茄炒出汁。','加水煮开后放入面条，按面条包装建议时间煮熟。加入鸡蛋和青菜，煮至食材熟透，少量加盐调味。'],
    pairing:'面条、鸡蛋和蔬菜同碗呈现，按自己的食量调整面条用量。剩余食材可接着用于下一餐。',
    cultureTitle:'把饮食记忆写进自己的做法',culture:'同样一碗面，有人先炒番茄，有人喜欢卧一个蛋。这一期留给日常：收藏后写下你家的顺序、口味和用量，让一份示范慢慢成为自己的做法。',
    references:[]
  }
]

export function editionDraft(edition) {
  const images=edition.image?[edition.image]:[]
  const diary=edition.diary?`节气日记 · ${edition.diary.term} · ${edition.diary.title}\n${edition.diary.text}\n${edition.diary.background}\n${edition.diary.reference.title} ${edition.diary.reference.url}\n日记文字：食拾原创` : ''
  return {schema_version:2,name:edition.name,emoji:edition.emoji,minutes:edition.minutes,servings:edition.servings,
    source:{platform:'manual',url:'',author:'食拾精选',original_text:[diary,edition.culture].filter(Boolean).join('\n\n'),original_images:[...images]},images,
    tags:edition.tags.map(name=>({name,group:'我的分类'})),
    ingredients:edition.ingredients.map(([name,amount])=>({id:newId(),name,amount,kind:['油','盐','姜'].includes(name)?'调料':'食材'})),
    steps:edition.steps.map(text=>({id:newId(),text,images:[]})),
    notes:`食拾每日精选 · ${edition.date} · 家常示范做法${diary?'\n\n'+diary:''}\n\n搭配：${edition.pairing}\n\n${edition.cultureTitle}：${edition.culture}${edition.references.length?'\n\n文化资料：\n'+edition.references.map(r=>r.title+' '+r.url).join('\n'):''}`}
}
