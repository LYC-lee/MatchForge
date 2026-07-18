<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppButton from '@/components/ui/AppButton.vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const account = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

function submit() {
  error.value = ''
  loading.value = true
  setTimeout(() => {
    const r = auth.login(account.value, password.value)
    loading.value = false
    if (r.ok) {
      const redirect = (route.query.redirect as string) || '/app'
      router.push(redirect)
    } else {
      error.value = r.msg || '登录失败'
    }
  }, 300)
}

function demoLogin() {
  account.value = 'demo@matchforge.ai'
  password.value = 'demo12345'
  submit()
}

function switchAccount() {
  auth.logout()
  account.value = ''
  password.value = ''
  error.value = ''
}

// ── 全息投影动画 ──
onMounted(() => {
  const c = document.getElementById('holoCanvas') as HTMLCanvasElement | null
  if (!c) return
  const ctx = c.getContext('2d')!
  let W = 0, H = 0

  function resize() {
    const r = c.parentElement!.getBoundingClientRect()
    const dpr = devicePixelRatio || 1
    c.width = r.width * dpr
    c.height = r.height * dpr
    c.style.width = r.width + 'px'
    c.style.height = r.height + 'px'
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    W = r.width; H = r.height
  }
  resize()
  window.addEventListener('resize', resize)

  const toR = (d: number) => d * Math.PI / 180

  function proj(lat: number, lng: number) {
    const p = toR(lat), l = toR(lng), p0 = toR(35), l0 = toR(103)
    const cp = Math.cos(p), sp = Math.sin(p), cd = Math.cos(l - l0), sd = Math.sin(l - l0)
    const cp0 = Math.cos(p0), sp0 = Math.sin(p0)
    const x3 = cp * sd, y3 = cp0 * sp - sp0 * cp * cd, z3 = sp0 * sp + cp0 * cp * cd
    if (z3 < 0) return null
    const s = Math.min(W, H) * 0.95, ox = W / 2, oy = H / 2 + 10
    return { x: ox + x3 * s, y: oy - y3 * s, z: z3 }
  }

  // 中国版图数据 (压缩)
  const P: number[][] = [
    [21.5081,107.9727],[21.6334,108.5021],[21.9046,108.4799],[21.4403,109.0815],[21.6934,109.5215],[21.4806,109.9308],[20.9169,109.6626],[20.2637,110.1231],[20.46,110.5176],[20.9446,110.154],[21.3381,110.4109],[21.2141,110.5672],[21.5591,111.6027],[21.8497,111.9439],[21.7417,112.305],[21.978,112.3597],[21.7769,112.5863],[22.208,113.0888],[22.2226,113.5481],[22.912,113.3311],[23.1021,113.5197],[22.5119,114.0154],[22.365,113.9373],[22.2956,114.268],[22.541,114.266],[22.9459,116.4707],[23.6467,116.9106],[23.5886,117.3677],[24.2461,118.0561],[24.4743,117.8427],[24.6214,118.657],[25.2093,118.9775],[25.2322,119.2855],[25.4498,119.1801],[25.3912,119.6225],[26.0036,119.6188],[26.1218,119.1395],[26.0547,119.4631],[26.3342,119.8811],[26.785,119.5882],[26.6716,120.0867],[28.01,120.7477],[28.3267,121.1457],[28.2921,121.61],[29.1932,121.4871],[29.135,121.9178],[29.6059,121.9412],[29.4846,121.5062],[29.8704,122.0829],[30.3041,121.258],[30.2413,120.1946],[30.917,121.8779],[31.9837,120.7155],[31.9363,120.0359],[32.1059,120.5201],[31.8165,121.8563],[32.6614,120.8532],[34.274,120.2667],[34.8488,119.1653],[35.9844,120.2848],[36.2024,120.1833],[36.1299,120.6379],[36.6328,120.8108],[36.9595,121.9327],[36.8322,122.3409],[37.4028,122.667],[37.4604,121.6402],[37.8339,120.75],[37.1551,119.7605],[37.1383,119.2874],[37.3312,118.9526],[38.0428,118.94],[38.3117,117.7667],[38.8529,117.6167],[39.1913,117.8657],[39.1826,118.977],[39.7525,119.3911],[40.231,120.4791],[40.9013,121.1745],[40.9743,121.8349],[40.5418,122.275],[39.5447,121.2675],[39.3865,121.8185],[38.9208,121.1067],[38.7316,121.1636],[39.6008,122.84],[40.0041,124.3621],[40.9046,125.9891],[41.7249,126.7431],[41.3877,128.1494],[41.9875,128.0452],[42.0382,128.9234],[42.4481,129.6979],[42.9981,129.8982],[42.5354,130.527],[42.7271,130.4248],[42.9022,131.0686],[43.3781,131.2573],[44.8443,130.9816],[45.3269,131.8519],[45.1307,133.1135],[47.3022,134.1677],[47.7154,134.7523],[48.2539,134.6652],[48.4363,135.0834],[48.3734,134.2934],[48.1057,133.144],[47.715,132.4763],[47.7093,130.9619],[48.8612,130.5531],[49.3888,129.4981],[49.8018,127.5508],[50.209,127.5902],[53.0423,125.649],[53.5465,123.6078],[53.2846,120.9854],[52.7872,120.0945],[52.5667,120.6562],[52.0965,120.7498],[50.406,119.1637],[50.0664,119.2599],[49.5135,117.8734],[49.8238,116.6833],[47.8748,115.6164],[47.6869,115.8982],[47.8698,116.7605],[47.6522,117.3508],[47.9879,117.7684],[47.984,118.4984],[47.15,119.7111],[46.6722,119.8672],[46.5862,117.4381],[46.362,117.3334],[46.2898,116.5626],[45.4583,115.6811],[45.39,114.5602],[44.7457,113.587],[45.0641,111.898],[44.3673,111.4022],[43.7114,111.9332],[42.7737,110.4004],[42.4384,109.3398],[42.2887,106.77],[41.5955,104.982],[41.6587,104.4982],[41.877,104.4982],[41.7513,103.7111],[42.1581,102.1566],[42.5388,101.4953],[42.7204,96.3854],[44.2781,95.3503],[44.9445,93.5162],[45.1961,90.8772],[46.9545,90.8699],[47.8777,90.0279],[48.0025,89.0477],[48.5551,87.9797],[49.1623,87.8143],[49.0858,87.3229],[49.0497,86.8083],[48.5286,86.5494],[48.3851,85.7494],[47.0635,85.4848],[46.8307,84.7861],[47.1859,83.0295],[45.5949,82.3152],[45.1255,82.5215],[45.3494,81.692],[44.8838,79.8719],[44.7146,80.4815],[44.0973,80.3553],[43.1616,80.7857],[42.7345,80.2022],[42.19,80.2094],[41.0756,78.1234],[41.0242,76.9077],[40.3522,76.3186],[40.3058,75.6771],[40.6252,75.5556],[40.4826,74.8352],[40.0431,73.9916],[39.4489,73.6316],[38.6069,73.8017],[38.4603,74.8123],[37.3857,75.1188],[37.2316,74.8913],[37.1577,74.3722],[37.0222,74.5414],[36.6949,75.7722],[36.049,75.9123],[35.6617,76.7669],[35.4959,77.7994],[35.4798,78.0427],[34.6064,78.327],[34.3026,78.9701],[34.0134,78.7267],[32.5011,79.2193],[32.3582,78.9189],[32.597,78.7009],[32.5199,78.3896],[31.1,78.8077],[31.0136,79.7078],[30.1645,81.0103],[30.3268,82.0434],[29.1836,83.5835],[29.22,84.1014],[28.9118,84.2287],[28.5922,85.1591],[28.316,85.1225],[28.2774,85.6783],[27.9104,85.9945],[28.1144,86.137],[27.8383,87.1414],[27.8706,88.1098],[28.0069,88.8037],[27.3161,88.8914],[28.3112,89.9811],[28.0802,90.3527],[28.0784,91.273],[27.76,91.6319],[27.5577,91.5947],[27.2906,92.0834],[26.855,91.9983],[26.9527,92.647],[26.8801,93.1114],[27.0252,93.8173],[27.5814,94.2774],[27.7431,94.8859],[27.94,95.2863],[28.1423,95.3971],[28.2952,95.832],[28.2282,96.2755],[27.7475,97.0868],[27.9377,97.3352],[28.218,97.3225],[28.517,97.5992],[28.1859,98.0616],[27.5501,98.2988],[27.5725,98.6512],[26.7857,98.7385],[25.8636,98.6563],[25.2519,97.8195],[24.7748,97.5833],[23.911,97.5646],[24.1212,98.8351],[23.9051,98.6768],[23.1913,98.8638],[22.9591,99.5071],[22.126,99.193],[22.028,99.9177],[21.4805,100.1477],[21.7559,101.0798],[21.5675,101.1389],[21.1973,101.2479],[21.2126,101.8006],[22.2537,101.5245],[22.4953,101.7388],[22.3792,102.1274],[22.7509,102.4709],[22.4482,102.9819],[22.7698,103.3267],[22.5401,103.9415],[23.3452,105.2754],[22.9228,105.843],[22.7789,106.7803],[22.5014,106.5504],[21.9789,106.6636],[21.5081,107.9727],
    [19.9919,110.8888],[20.1377,110.6518],[19.8827,109.2635],[19.3041,108.6655],[18.5353,108.7016],[18.2183,109.5193],[18.4476,110.0674],[19.6555,111.0137],[19.9919,110.8888],
    [22.6204,121.0088],[23.1725,121.3975],[24.9737,121.929],[25.2753,121.5937],[25.0328,121.0406],[23.6529,120.1321],[22.7179,120.2328],[21.925,120.8398],[22.6204,121.0088],
    [25.9358,124.4751],[25.8592,124.4641],[25.9111,124.6536],[25.9655,124.5822],[25.9358,124.4751],[26.0025,123.7143],[25.921,123.5962],[25.8716,123.7198],[25.921,123.7967],[26.0025,123.7143],[25.7554,123.4946],[25.7306,123.327],[25.6712,123.2639],[25.6192,123.3325],[25.6861,123.5797],[25.7554,123.4946],[20.7717,116.7696],[20.6833,116.8897],[20.601,116.7493],[20.5886,116.8626],[20.7269,116.9255],[20.7717,116.7696],[16.552,111.7447],[16.4598,111.7392],[16.5125,111.7886],[16.552,111.7447],[7.6072,113.8969],[7.5378,114.0589],[7.6386,114.3687],[7.9458,114.5405],[7.6072,113.8969],[23.4608,122.5187],[24.5737,122.7986],[24.5786,122.7792],[23.4657,122.4993],[23.4608,122.5187],[11.1896,118.6865],[10.9126,118.524],[10.9029,118.5404],[11.1815,118.7048],[11.6075,118.8746],[11.9857,118.989],[11.9915,118.9698],[11.6137,118.8556],[11.1896,118.6865],[3.5349,112.3071],[3.4169,111.7869],[3.3974,111.7913],[3.5156,112.3125],[3.5786,112.5215],[3.7326,112.8521],[3.7507,112.8436],[3.5975,112.515],[3.5349,112.3071],[16.2621,111.8134],[16.2602,111.6623],[16.1619,111.5689],[16.2252,111.8161],[16.2621,111.8134],[16.059,112.6126],[16.0432,112.4615],[16.0009,112.4753],[16.059,112.6126],[7.3443,109.464],[7.523,109.9487],[7.5597,109.6531],[7.3443,109.464],[10.3957,116.4888],[10.3091,116.4672],[10.3351,116.6446],[10.3957,116.4888],[20.8055,121.172],[21.6874,121.9094],[21.7003,121.894],[20.8183,121.1567],[20.8055,121.172],[18.0071,119.4737],[19.024,120.0257],[19.0336,120.0081],[18.0166,119.4561],[18.0071,119.4737],[15.0075,119.0722],[16.0439,119.0727],[16.0439,119.0527],[15.0078,119.0522],[15.0075,119.0722],[7.1467,115.5447],[7.9793,116.2505],[7.9922,116.2352],[7.1597,115.5294],[7.1467,115.5447],[6.0127,108.2901],[6.0199,108.3088],[6.0954,108.2796],[6.2275,108.2561],[6.5382,108.2168],[6.9496,108.2188],[7.0739,108.2442],[7.0779,108.2246],[6.9507,108.1988],[6.5376,108.1968],[6.2248,108.2363],[6.091,108.26],[6.0127,108.2901],[11.3689,110.1282],[11.2534,110.0555],[11.2427,110.0725],[11.3595,110.1459],[11.4813,110.207],[11.605,110.259],[11.7836,110.3046],[11.9457,110.3282],[12.1416,110.3342],[12.2404,110.3323],[12.24,110.3123],[12.142,110.3142],[11.948,110.3084],[11.7871,110.2849],[11.6107,110.2398],[11.49,110.189],[11.3689,110.1282],[15.1532,109.8452],[15.1572,109.8648],[15.2339,109.8489],[15.4507,109.7897],[15.6755,109.6901],[15.8368,109.5915],[15.9226,109.532],[16.2073,109.3089],[16.1949,109.2931],[15.911,109.5157],[15.8261,109.5746],[15.6656,109.6726],[15.4447,109.7707],[15.229,109.8295],[15.1532,109.8452]
  ]
  const PI = [0,268,277,286,291,296,302,308,312,317,322,331,340,345,349,353,357,362,367,372,377,390,407]
  const chinaPolys = PI.map((s, i, a) => P.slice(s, a[i+1] || P.length)).filter(p => p.length > 2)

  const cities = [
    {name:'深圳',lat:22.5,lng:114.1},{name:'上海',lat:31.2,lng:121.5},{name:'北京',lat:39.9,lng:116.4},
    {name:'成都',lat:30.6,lng:104.1},{name:'广州',lat:23.1,lng:113.3},{name:'武汉',lat:30.6,lng:114.3},
    {name:'杭州',lat:30.3,lng:120.2},{name:'西安',lat:34.3,lng:108.9},{name:'重庆',lat:29.6,lng:106.5},
    {name:'南京',lat:32.1,lng:118.8},{name:'东莞',lat:23.0,lng:113.8},
  ]

  // 中国版图上下边界
  let minLat = 90, maxLat = -90
  chinaPolys.forEach(poly => poly.forEach(([lat]) => { if(lat < minLat) minLat = lat; if(lat > maxLat) maxLat = lat }))
  let cnMinY = 0, cnMaxY = 0
  function calcCnBounds() { const t = proj(maxLat, 103); const b = proj(minLat, 103); cnMinY = t ? t.y : 0; cnMaxY = b ? b.y : 0 }
  calcCnBounds()

  // 粒子
  const plist: any[] = []
  class Pt {
    f: any; t: any; p: number; spd: number; s: number; oy: number; op: number; h: number; delay: number
    constructor() {
      this.f = cities[Math.random() * cities.length | 0]
      this.t = cities[Math.random() * cities.length | 0]
      while (this.t === this.f) this.t = cities[Math.random() * cities.length | 0]
      this.p = Math.random(); this.spd = 0.001 + Math.random() * 0.003
      this.s = 1.5 + Math.random() * 2; this.oy = (Math.random() - 0.5) * 25
      this.op = 0.3 + Math.random() * 0.5; this.h = 220 + Math.random() * 40
      this.delay = Math.random() * 100
    }
    update() {
      if (this.delay > 0) { this.delay--; return }
      this.p += this.spd; if (this.p > 1) { this.p = 0; this.delay = Math.random() * 80 }
    }
    draw(time: number) {
      if (this.delay > 0) return
      const p1 = proj(this.f.lat, this.f.lng), p2 = proj(this.t.lat, this.t.lng)
      if (!p1 || !p2) return
      const p = this.p, cx = (p1.x + p2.x) / 2, cy = (p1.y + p2.y) / 2 - 15 + this.oy
      const x = (1-p)*(1-p)*p1.x + 2*(1-p)*p*cx + p*p*p2.x, y = (1-p)*(1-p)*p1.y + 2*(1-p)*p*cy + p*p*p2.y
      const a = Math.sin(p * Math.PI) * this.op, r = this.s * (0.5 + 0.5 * Math.sin(p * Math.PI))
      const g = ctx.createRadialGradient(x, y, 0, x, y, r * 6)
      g.addColorStop(0, `hsla(${this.h},80%,70%,${a * 0.15})`); g.addColorStop(1, 'transparent')
      ctx.beginPath(); ctx.arc(x, y, r * 6, 0, 6.28); ctx.fillStyle = g; ctx.fill()
      ctx.beginPath(); ctx.arc(x, y, r, 0, 6.28); ctx.fillStyle = `hsla(${this.h},80%,70%,${a})`; ctx.fill()
      for (let j = 1; j <= 3; j++) {
        const tp = p - j * 0.025; if (tp <= 0) continue
        const tx = (1-tp)*(1-tp)*p1.x + 2*(1-tp)*tp*cx + tp*tp*p2.x, ty = (1-tp)*(1-tp)*p1.y + 2*(1-tp)*tp*cy + tp*tp*p2.y
        const ta = Math.sin(tp * Math.PI) * this.op * (0.1 - j * 0.025)
        ctx.beginPath(); ctx.arc(tx, ty, r * (1 - j * 0.2), 0, 6.28)
        ctx.fillStyle = `hsla(${this.h},80%,70%,${Math.max(0, ta)})`; ctx.fill()
      }
    }
  }
  for (let i = 0; i < 20; i++) plist.push(new Pt())

  // 动画
  let animId = 0
  function draw(t: number) {
    const time = t * 0.001
    ctx.clearRect(0, 0, W, H)
    const cx = W / 2, cy = H / 2 + 10, ps = Math.min(W, H) * 0.95, px = cx, py = H - 25

    // 1. 投影仪底座
    const bg = ctx.createRadialGradient(px, py, 0, px, py, 35)
    bg.addColorStop(0, `rgba(99,102,241,${0.15+0.05*Math.sin(time*0.5)})`)
    bg.addColorStop(0.4, `rgba(99,102,241,${0.06})`); bg.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.fillStyle = bg; ctx.fillRect(px - 35, py - 35, 70, 45)
    ctx.strokeStyle = `rgba(99,102,241,${0.12+0.04*Math.sin(time*0.7)})`; ctx.lineWidth = 1.5
    ctx.beginPath(); ctx.arc(px, py, 12, 0, 6.28); ctx.stroke()
    ctx.strokeStyle = `rgba(167,139,250,${0.08})`; ctx.lineWidth = 0.8
    ctx.beginPath(); ctx.arc(px, py, 18, 0, 6.28); ctx.stroke()

    // 2. 线性光束
    const cnRange = (cnMaxY - cnMinY) / 2 + 20
    const cnCenter = (cnMaxY + cnMinY) / 2
    const scanY2 = cnCenter + Math.sin(time * 0.35) * cnRange
    const beamTop = Math.max(cnMinY - 30, Math.min(cnMaxY, scanY2))
    const beamWidth = ps * 0.5

    ctx.save()
    ctx.beginPath(); ctx.moveTo(px - 4, py); ctx.lineTo(px + 4, py)
    ctx.lineTo(cx + beamWidth, beamTop); ctx.lineTo(cx - beamWidth, beamTop); ctx.closePath()
    const beamGrad = ctx.createLinearGradient(px, py, cx, beamTop)
    beamGrad.addColorStop(0, `rgba(130,130,255,${0.12+0.03*Math.sin(time*0.4)})`)
    beamGrad.addColorStop(0.2, `rgba(100,100,230,${0.07})`); beamGrad.addColorStop(0.4, `rgba(80,80,200,${0.04})`)
    beamGrad.addColorStop(0.6, `rgba(60,60,160,${0.02})`); beamGrad.addColorStop(0.8, `rgba(40,40,120,${0.008})`)
    beamGrad.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.fillStyle = beamGrad; ctx.fill(); ctx.restore()

    // 3. 经纬网格 + 球体边缘
    ctx.strokeStyle = 'rgba(99,102,241,0.08)'; ctx.lineWidth = 0.5
    ctx.beginPath(); ctx.arc(cx, cy, ps, 0, 6.28); ctx.stroke()
    ctx.strokeStyle = 'rgba(99,102,241,0.10)'; ctx.lineWidth = 0.6
    for (let lng = 70; lng <= 140; lng += 5) {
      const pts: any[] = []; let ok = true
      for (let lat = 0; lat <= 60; lat += 1) { const p = proj(lat, lng); if (!p) { ok = false; break } pts.push(p) }
      if (!ok || pts.length < 2) continue; ctx.beginPath(); pts.forEach((p, i) => { i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y) }); ctx.stroke()
    }
    for (let lat = 0; lat <= 60; lat += 5) {
      const pts: any[] = []; let ok = true
      for (let lng = 65; lng <= 145; lng += 1) { const p = proj(lat, lng); if (!p) { ok = false; break } pts.push(p) }
      if (!ok || pts.length < 2) continue; ctx.beginPath(); pts.forEach((p, i) => { i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y) }); ctx.stroke()
    }

    // 4. 全息中国版图 (仅轮廓)
    chinaPolys.forEach(poly => {
      const pts: any[] = []; let ok = true
      for (const p of poly) { const gp = proj(p[0], p[1]); if (!gp) { ok = false; break } pts.push(gp) }
      if (!ok || pts.length < 3) return
      ctx.beginPath(); pts.forEach((p, i) => { i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y) }); ctx.closePath()
      ctx.save(); ctx.shadowColor = `rgba(99,102,241,${0.25+0.12*Math.sin(time*0.6)})`; ctx.shadowBlur = 20 + 10 * Math.sin(time * 0.6)
      ctx.strokeStyle = `rgba(129,140,248,${0.4+0.12*Math.sin(time*0.6)})`; ctx.lineWidth = 1.3; ctx.stroke(); ctx.restore()
      ctx.strokeStyle = `rgba(99,102,241,${0.5+0.15*Math.sin(time*0.8)})`; ctx.lineWidth = 0.7; ctx.stroke()
    })

    // 5. 扫描线
    ctx.save(); ctx.beginPath(); ctx.arc(cx, cy, ps, 0, 6.28); ctx.clip()
    const scanY = scanY2
    ctx.strokeStyle = `rgba(150,150,255,${0.05+0.02*Math.sin(time*0.3)})`; ctx.lineWidth = 1.5
    ctx.beginPath(); ctx.moveTo(0, scanY); ctx.lineTo(W, scanY); ctx.stroke()
    ctx.restore()

    // 6. 城市光点 + 连线
    for (let i = 0; i < cities.length; i++) { for (let j = i + 1; j < cities.length; j++) { if (Math.random() > 0.1) continue;
      const p1 = proj(cities[i].lat, cities[i].lng), p2 = proj(cities[j].lat, cities[j].lng)
      if (!p1 || !p2) continue; ctx.beginPath(); ctx.moveTo(p1.x, p1.y)
      ctx.quadraticCurveTo((p1.x+p2.x)/2, (p1.y+p2.y)/2-10, p2.x, p2.y)
      ctx.strokeStyle = `rgba(99,102,241,${0.015+0.01*Math.sin(time+i)})`; ctx.lineWidth = 0.5; ctx.stroke() } }
    cities.forEach(city => {
      const pos = proj(city.lat, city.lng); if (!pos) return
      const a = Math.min(1, Math.max(0.3, (pos.z + 0.3) / 1.3))
      const gg = ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, 10)
      gg.addColorStop(0, `rgba(99,102,241,${0.08*a})`); gg.addColorStop(1, 'transparent')
      ctx.beginPath(); ctx.arc(pos.x, pos.y, 10, 0, 6.28); ctx.fillStyle = gg; ctx.fill()
      ctx.beginPath(); ctx.arc(pos.x, pos.y, 2.5+Math.sin(time*1.5+city.lng), 0, 6.28)
      ctx.strokeStyle = `rgba(167,139,250,${0.12*a})`; ctx.lineWidth = 0.8; ctx.stroke()
      ctx.beginPath(); ctx.arc(pos.x, pos.y, 2, 0, 6.28); ctx.fillStyle = `rgba(199,210,254,${0.8*a})`; ctx.fill()
      ctx.fillStyle = `rgba(255,255,255,${0.3*a})`; ctx.font = '10px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'top'
      ctx.fillText(city.name, pos.x, pos.y + 5)
    })

    // 7. 粒子
    plist.forEach(p => { p.update(); (p as any).draw(time) })

    animId = requestAnimationFrame(draw)
  }
  animId = requestAnimationFrame(draw)
})
</script>

<template>
  <div class="auth-page">
    <section class="auth-story">
      <canvas id="holoCanvas" class="auth-canvas" />
      <div class="auth-overlay">
        <div class="auth-brand">
          <span class="auth-brand__mark"><svg viewBox="0 0 48 46" class="brand__logo" aria-hidden="true"><path d="M25.946 44.938c-.664.845-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.287c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.497 0-3.578-1.842-3.578H1.237c-.92 0-1.456-1.04-.92-1.788L10.013.474c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.579 1.842 3.579h11.377c.943 0 1.473 1.088.89 1.83L25.947 44.94z" fill="currentColor"/></svg></span>
          <span class="auth-brand__text">MatchForge · 智配</span>
        </div>
        <p class="auth-story__eyebrow">AI Sourcing Workspace</p>
        <h1 class="auth-story__title">把缺货寻源拆成可追踪的采购工作流</h1>
        <p class="auth-story__copy">
          规格解析、替代料分级、供应商能力匹配和 RFQ 生成被清晰分隔在一个 Linear 风格工作台里。
        </p>
        <div class="auth-story__metrics">
          <div><b>6</b><span>智能体阶段</span></div>
          <div><b>L1-L5</b><span>替代风险分级</span></div>
          <div><b>RFQ</b><span>可编辑询价单</span></div>
        </div>
      </div>
    </section>

    <section class="auth-panel">
      <div class="auth-card">
        <RouterLink to="/" class="auth-back">← 返回产品介绍</RouterLink>
        <div class="auth-brand auth-card__brand">
          <span class="auth-brand__mark"><svg viewBox="0 0 48 46" class="brand__logo" aria-hidden="true"><path d="M25.946 44.938c-.664.845-2.021.375-2.021-.698V33.937a2.26 2.26 0 0 0-2.262-2.262H10.287c-.92 0-1.456-1.04-.92-1.788l7.48-10.471c1.07-1.497 0-3.578-1.842-3.578H1.237c-.92 0-1.456-1.04-.92-1.788L10.013.474c.214-.297.556-.474.92-.474h28.894c.92 0 1.456 1.04.92 1.788l-7.48 10.471c-1.07 1.498 0 3.579 1.842 3.579h11.377c.943 0 1.473 1.088.89 1.83L25.947 44.94z" fill="currentColor"/></svg></span>
          <span class="auth-brand__text">MatchForge · 智配</span>
        </div>

        <h2 class="auth-card__title">登录</h2>
        <p class="auth-card__sub">进入 AI 元器件替代料寻源工作台</p>

        <div v-if="auth.isAuthenticated" class="auth-session">
          <span class="auth-session__avatar">{{ auth.user?.name.slice(0, 1).toUpperCase() }}</span>
          <div>
            <b>已登录：{{ auth.user?.name }}</b>
            <p>{{ auth.user?.account }}</p>
          </div>
          <RouterLink to="/app" class="auth-session__cta">进入工作台</RouterLink>
          <button type="button" class="auth-session__switch" @click="switchAccount">切换账号</button>
        </div>

        <form v-else class="auth-form" @submit.prevent="submit">
          <label class="auth-field">
            <span class="auth-field__label">账号</span>
            <input v-model="account" type="text" class="auth-input" placeholder="name@company.com" autocomplete="username" />
          </label>
          <label class="auth-field">
            <span class="auth-field__label">密码</span>
            <input v-model="password" type="password" class="auth-input" placeholder="输入密码" autocomplete="current-password" />
          </label>
          <p v-if="error" class="auth-error">{{ error }}</p>
          <AppButton type="submit" size="lg" :loading="loading" :disabled="loading" class="auth-submit">登录</AppButton>
          <button type="button" class="auth-demo" @click="demoLogin">使用演示账号登录</button>
        </form>

        <p class="auth-hint">还没有账号? <RouterLink to="/register">创建采购工作台</RouterLink></p>
        <div class="auth-disclaimer">演示账号：demo@matchforge.ai / demo12345。本地 mock 认证仅用于 Spike 演示，生产环境应由后端签发 HttpOnly Cookie 或短期 Token。</div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 440px;
  overflow: hidden;
  background: #05070a;
}
.auth-story {
  position: relative;
  padding: clamp(40px, 8vw, 96px);
  border-right: 1px solid var(--border-default);
  overflow: hidden;
  background:
    radial-gradient(ellipse at 50% 60%, rgba(8,12,30,0.8), #030408);
}
.auth-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 1;
}
.auth-overlay {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  justify-content: center;
  height: 100%;
}
.auth-story .auth-brand {
  margin-bottom: var(--space-8);
}
.auth-story__eyebrow {
  margin-bottom: var(--space-3);
  color: var(--accent-hover);
  font-size: var(--font-size-xs);
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}
.auth-story__title {
  max-width: 680px;
  color: #f4f7ff;
  font-size: clamp(36px, 6vw, 64px);
  line-height: 1.04;
  letter-spacing: -0.05em;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.04);
}
.auth-story__copy {
  max-width: 560px;
  margin-top: var(--space-5);
  color: #c2c7d4;
  font-size: var(--font-size-lg);
}
.auth-story__metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
  max-width: 680px;
  margin-top: var(--space-8);
}
.auth-story__metrics div {
  position: relative;
  overflow: hidden;
  min-height: 86px;
  padding: var(--space-4);
  border: 1px solid rgba(129, 140, 248, 0.34);
  border-radius: 12px;
  background:
    radial-gradient(circle at 12% 16%, rgba(129, 140, 248, 0.22), transparent 34%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.075), rgba(255, 255, 255, 0.028)),
    #121622;
  box-shadow: 0 12px 34px rgba(0, 0, 0, 0.28);
}
.auth-story__metrics div::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: var(--gradient-accent);
}
.auth-story__metrics div::after {
  content: '';
  position: absolute;
  right: 12px;
  top: 12px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: rgba(129, 140, 248, 0.24);
  box-shadow: 0 0 26px rgba(129, 140, 248, 0.3);
}
.auth-story__metrics b {
  display: block;
  margin-bottom: var(--space-1);
  font-family: var(--font-mono);
  color: #f4f7ff;
  font-size: var(--font-size-xl);
  line-height: 1.1;
}
.auth-story__metrics span {
  color: #c5cada;
  font-size: var(--font-size-sm);
  line-height: 1.45;
}
.auth-brand {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.auth-brand__mark {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  background: var(--gradient-accent);
  box-shadow: 0 0 28px rgba(99, 102, 241, 0.24);
  color: #fff;
}
.auth-brand__text {
  color: #f4f7ff;
  font-weight: 700;
}
.auth-story .auth-brand {
  margin-bottom: var(--space-8);
}
.auth-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-5);
  background: #0f1117;
}
.auth-card {
  width: 100%;
  max-width: 380px;
  padding: var(--space-6);
  border: 1px solid #343a4d;
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.045), rgba(255, 255, 255, 0.015)), #10131b;
  box-shadow: var(--shadow-lg);
}
.auth-back { display: inline-flex; margin-bottom: var(--space-5); color: #aeb5c4; font-size: var(--font-size-sm); }
.auth-back:hover { color: #f4f7ff; }
.auth-card__brand { margin-bottom: var(--space-6); }
.auth-card__title { margin-bottom: var(--space-1); color: #f4f7ff; font-size: var(--font-size-2xl); }
.auth-card__sub { margin-bottom: var(--space-5); color: #aeb5c4; font-size: var(--font-size-sm); }
.auth-form { display: flex; flex-direction: column; gap: var(--space-3); }
.auth-session { display: grid; grid-template-columns: 42px minmax(0, 1fr); gap: var(--space-3); padding: var(--space-4); border: 1px solid var(--border-default); border-radius: var(--radius-lg); background: rgba(255, 255, 255, 0.045); }
.auth-session__avatar { width: 42px; height: 42px; display: inline-flex; align-items: center; justify-content: center; border-radius: 50%; color: #fff; background: var(--gradient-accent); font-weight: 700; }
.auth-session b { display: block; color: #f4f7ff; font-size: var(--font-size-sm); }
.auth-session p { margin-top: 2px; color: #aeb5c4; font-size: var(--font-size-xs); }
.auth-session__cta, .auth-session__switch { grid-column: 1 / -1; height: 36px; display: inline-flex; align-items: center; justify-content: center; border-radius: var(--radius-md); font-size: var(--font-size-sm); font-weight: 600; }
.auth-session__cta { color: #fff; background: var(--accent); }
.auth-session__switch { color: #c5cada; background: #151924; border: 1px solid #343a4d; }
.auth-field { display: flex; flex-direction: column; gap: var(--space-1); }
.auth-field__label { color: #c5cada; font-size: var(--font-size-xs); font-weight: 600; }
.auth-input { height: 40px; padding: 0 12px; color: #f4f7ff; background: #151924; border: 1px solid #343a4d; border-radius: var(--radius-md); outline: none; transition: border-color var(--transition-fast), box-shadow var(--transition-fast); }
.auth-input:focus { border-color: var(--accent-border); box-shadow: 0 0 0 3px var(--accent-soft); }
.auth-input::placeholder { color: #7f8799; }
.auth-error { padding: 6px 10px; color: var(--danger); background: var(--danger-soft); border-radius: var(--radius-sm); font-size: var(--font-size-xs); }
.auth-submit { width: 100%; margin-top: var(--space-2); }
.auth-demo { width: 100%; padding: 8px; color: #c5cada; border-radius: var(--radius-md); font-size: var(--font-size-sm); transition: all var(--transition-fast); }
.auth-demo:hover { color: #f4f7ff; background: var(--accent-soft); }
.auth-hint { margin-top: var(--space-4); text-align: center; color: #aeb5c4; font-size: var(--font-size-xs); }
.auth-hint a { font-weight: 700; }
.auth-disclaimer { margin-top: var(--space-4); padding-top: var(--space-4); color: #9aa3b7; border-top: 1px solid var(--border-subtle); font-size: var(--font-size-xs); line-height: 1.6; }

@media (max-width: 960px) {
  .auth-page { grid-template-columns: 1fr; }
  .auth-story { display: none; }
}
</style>
