<script setup lang="ts">
/**
 * 全息中国地图背景（登录/注册页 story 面板）。
 * - 配色收敛到设计令牌：读取 --accent / --warning / --text-tertiary，hex→rgba 按需取 alpha
 * - prefers-reduced-motion：静态绘制一帧，不启动 rAF 循环（暂停按钮隐藏）
 * - 提供暂停按钮；主题切换时重读令牌颜色并重绘
 * - canvas 绝对定位铺满父容器（父需 position:relative 且有尺寸）
 */
import { onMounted, onUnmounted, ref } from 'vue'

const canvasRef = ref<HTMLCanvasElement | null>(null)
const paused = ref(false)
const reduced = ref(false)

let animId = 0
let ro: ResizeObserver | null = null
let themeObserver: MutationObserver | null = null
let arrows: any[] = []
// draw 闭包由 onMounted 注入，供 togglePause 重启循环
let drawFn: ((t: number) => void) | null = null

const colors = { accent: '#6366f1', warning: '#b45309', tertiary: '#8e8e99' }

function readColors() {
  const cs = getComputedStyle(document.documentElement)
  colors.accent = cs.getPropertyValue('--accent').trim() || colors.accent
  colors.warning = cs.getPropertyValue('--warning').trim() || colors.warning
  colors.tertiary = cs.getPropertyValue('--text-tertiary').trim() || colors.tertiary
}
function hexToRgb(hex: string): [number, number, number] {
  let h = hex.replace('#', '').trim()
  if (h.length === 3) h = h.split('').map((c) => c + c).join('')
  const n = parseInt(h, 16)
  if (Number.isNaN(n)) return [99, 102, 241]
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}
function rgba(hex: string, a: number): string {
  const [r, g, b] = hexToRgb(hex)
  return `rgba(${r},${g},${b},${a})`
}

onMounted(() => {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')!
  // 闭包内 TS 不再窄化 ref，固定一个非空引用
  const cv: HTMLCanvasElement = canvas
  let W = 0, H = 0

  readColors()
  reduced.value = window.matchMedia('(prefers-reduced-motion: reduce)').matches

  function resize() {
    const r = cv.parentElement!.getBoundingClientRect()
    const dpr = Math.min(devicePixelRatio || 1, 2)
    cv.width = r.width * dpr
    cv.height = r.height * dpr
    cv.style.width = r.width + 'px'
    cv.style.height = r.height + 'px'
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    W = r.width
    H = r.height
  }
  resize()
  ro = new ResizeObserver(resize)
  ro.observe(cv.parentElement!)

  const toR = (d: number) => (d * Math.PI) / 180
  const proj = (lat: number, lng: number) => {
    const p = toR(lat), l = toR(lng), p0 = toR(35), l0 = toR(103)
    const cp = Math.cos(p), sp = Math.sin(p), cd = Math.cos(l - l0), sd = Math.sin(l - l0), cp0 = Math.cos(p0), sp0 = Math.sin(p0)
    const x3 = cp * sd, y3 = cp0 * sp - sp0 * cp * cd, z3 = sp0 * sp + cp0 * cp * cd
    if (z3 < 0) return null
    const s = Math.min(W, H) * 0.95, ox = W / 2, oy = H / 2 - 15
    return { x: ox + x3 * s, y: oy - y3 * s, z: z3 }
  }

  // 中国版图数据
  const P: number[][] = [
    [21.5081,107.9727],[21.6334,108.5021],[21.9046,108.4799],[21.4403,109.0815],[21.6934,109.5215],[21.4806,109.9308],[20.9169,109.6626],[20.2637,110.1231],[20.46,110.5176],[20.9446,110.154],[21.3381,110.4109],[21.2141,110.5672],[21.5591,111.6027],[21.8497,111.9439],[21.7417,112.305],[21.978,112.3597],[21.7769,112.5863],[22.208,113.0888],[22.2226,113.5481],[22.912,113.3311],[23.1021,113.5197],[22.5119,114.0154],[22.365,113.9373],[22.2956,114.268],[22.541,114.266],[22.9459,116.4707],[23.6467,116.9106],[23.5886,117.3677],[24.2461,118.0561],[24.4743,117.8427],[24.6214,118.657],[25.2093,118.9775],[25.2322,119.2855],[25.4498,119.1801],[25.3912,119.6225],[26.0036,119.6188],[26.1218,119.1395],[26.0547,119.4631],[26.3342,119.8811],[26.785,119.5882],[26.6716,120.0867],[28.01,120.7477],[28.3267,121.1457],[28.2921,121.61],[29.1932,121.4871],[29.135,121.9178],[29.6059,121.9412],[29.4846,121.5062],[29.8704,122.0829],[30.3041,121.258],[30.2413,120.1946],[30.917,121.8779],[31.9837,120.7155],[31.9363,120.0359],[32.1059,120.5201],[31.8165,121.8563],[32.6614,120.8532],[34.274,120.2667],[34.8488,119.1653],[35.9844,120.2848],[36.2024,120.1833],[36.1299,120.6379],[36.6328,120.8108],[36.9595,121.9327],[36.8322,122.3409],[37.4028,122.667],[37.4604,121.6402],[37.8339,120.75],[37.1551,119.7605],[37.1383,119.2874],[37.3312,118.9526],[38.0428,118.94],[38.3117,117.7667],[38.8529,117.6167],[39.1913,117.8657],[39.1826,118.977],[39.7525,119.3911],[40.231,120.4791],[40.9013,121.1745],[40.9743,121.8349],[40.5418,122.275],[39.5447,121.2675],[39.3865,121.8185],[38.9208,121.1067],[38.7316,121.1636],[39.6008,122.84],[40.0041,124.3621],[40.9046,125.9891],[41.7249,126.7431],[41.3877,128.1494],[41.9875,128.0452],[42.0382,128.9234],[42.4481,129.6979],[42.9981,129.8982],[42.5354,130.527],[42.7271,130.4248],[42.9022,131.0686],[43.3781,131.2573],[44.8443,130.9816],[45.3269,131.8519],[45.1307,133.1135],[47.3022,134.1677],[47.7154,134.7523],[48.2539,134.6652],[48.4363,135.0834],[48.3734,134.2934],[48.1057,133.144],[47.715,132.4763],[47.7093,130.9619],[48.8612,130.5531],[49.3888,129.4981],[49.8018,127.5508],[50.209,127.5902],[53.0423,125.649],[53.5465,123.6078],[53.2846,120.9854],[52.7872,120.0945],[52.5667,120.6562],[52.0965,120.7498],[50.406,119.1637],[50.0664,119.2599],[49.5135,117.8734],[49.8238,116.6833],[47.8748,115.6164],[47.6869,115.8982],[47.8698,116.7605],[47.6522,117.3508],[47.9879,117.7684],[47.984,118.4984],[47.15,119.7111],[46.6722,119.8672],[46.5862,117.4381],[46.362,117.3334],[46.2898,116.5626],[45.4583,115.6811],[45.39,114.5602],[44.7457,113.587],[45.0641,111.898],[44.3673,111.4022],[43.7114,111.9332],[42.7737,110.4004],[42.4384,109.3398],[42.2887,106.77],[41.5955,104.982],[41.6587,104.4982],[41.877,104.4982],[41.7513,103.7111],[42.1581,102.1566],[42.5388,101.4953],[42.7204,96.3854],[44.2781,95.3503],[44.9445,93.5162],[45.1961,90.8772],[46.9545,90.8699],[47.8777,90.0279],[48.0025,89.0477],[48.5551,87.9797],[49.1623,87.8143],[49.0858,87.3229],[49.0497,86.8083],[48.5286,86.5494],[48.3851,85.7494],[47.0635,85.4848],[46.8307,84.7861],[47.1859,83.0295],[45.5949,82.3152],[45.1255,82.5215],[45.3494,81.692],[44.8838,79.8719],[44.7146,80.4815],[44.0973,80.3553],[43.1616,80.7857],[42.7345,80.2022],[42.19,80.2094],[41.0756,78.1234],[41.0242,76.9077],[40.3522,76.3186],[40.3058,75.6771],[40.6252,75.5556],[40.4826,74.8352],[40.0431,73.9916],[39.4489,73.6316],[38.6069,73.8017],[38.4603,74.8123],[37.3857,75.1188],[37.2316,74.8913],[37.1577,74.3722],[37.0222,74.5414],[36.6949,75.7722],[36.049,75.9123],[35.6617,76.7669],[35.4959,77.7994],[35.4798,78.0427],[34.6064,78.327],[34.3026,78.9701],[34.0134,78.7267],[32.5011,79.2193],[32.3582,78.9189],[32.597,78.7009],[32.5199,78.3896],[31.1,78.8077],[31.0136,79.7078],[30.1645,81.0103],[30.3268,82.0434],[29.1836,83.5835],[29.22,84.1014],[28.9118,84.2287],[28.5922,85.1591],[28.316,85.1225],[28.2774,85.6783],[27.9104,85.9945],[28.1144,86.137],[27.8383,87.1414],[27.8706,88.1098],[28.0069,88.8037],[27.3161,88.8914],[28.3112,89.9811],[28.0802,90.3527],[28.0784,91.273],[27.76,91.6319],[27.5577,91.5947],[27.2906,92.0834],[26.855,91.9983],[26.9527,92.647],[26.8801,93.1114],[27.0252,93.8173],[27.5814,94.2774],[27.7431,94.8859],[27.94,95.2863],[28.1423,95.3971],[28.2952,95.832],[28.2282,96.2755],[27.7475,97.0868],[27.9377,97.3352],[28.218,97.3225],[28.517,97.5992],[28.1859,98.0616],[27.5501,98.2988],[27.5725,98.6512],[26.7857,98.7385],[25.8636,98.6563],[25.2519,97.8195],[24.7748,97.5833],[23.911,97.5646],[24.1212,98.8351],[23.9051,98.6768],[23.1913,98.8638],[22.9591,99.5071],[22.126,99.193],[22.028,99.9177],[21.4805,100.1477],[21.7559,101.0798],[21.5675,101.1389],[21.1973,101.2479],[21.2126,101.8006],[22.2537,101.5245],[22.4953,101.7388],[22.3792,102.1274],[22.7509,102.4709],[22.4482,102.9819],[22.7698,103.3267],[22.5401,103.9415],[23.3452,105.2754],[22.9228,105.843],[22.7789,106.7803],[22.5014,106.5504],[21.9789,106.6636],[21.5081,107.9727],
    [19.9919,110.8888],[20.1377,110.6518],[19.8827,109.2635],[19.3041,108.6655],[18.5353,108.7016],[18.2183,109.5193],[18.4476,110.0674],[19.6555,111.0137],[19.9919,110.8888],
    [22.6204,121.0088],[23.1725,121.3975],[24.9737,121.929],[25.2753,121.5937],[25.0328,121.0406],[23.6529,120.1321],[22.7179,120.2328],[21.925,120.8398],[22.6204,121.0088],
    [25.9358,124.4751],[25.8592,124.4641],[25.9111,124.6536],[25.9655,124.5822],[25.9358,124.4751],[26.0025,123.7143],[25.921,123.5962],[25.8716,123.7198],[25.921,123.7967],[26.0025,123.7143],[25.7554,123.4946],[25.7306,123.327],[25.6712,123.2639],[25.6192,123.3325],[25.6861,123.5797],[25.7554,123.4946],[20.7717,116.7696],[20.6833,116.8897],[20.601,116.7493],[20.5886,116.8626],[20.7269,116.9255],[20.7717,116.7696],[16.552,111.7447],[16.4598,111.7392],[16.5125,111.7886],[16.552,111.7447],[7.6072,113.8969],[7.5378,114.0589],[7.6386,114.3687],[7.9458,114.5405],[7.6072,113.8969],[23.4608,122.5187],[24.5737,122.7986],[24.5786,122.7792],[23.4657,122.4993],[23.4608,122.5187],[11.1896,118.6865],[10.9126,118.524],[10.9029,118.5404],[11.1815,118.7048],[11.6075,118.8746],[11.9857,118.989],[11.9915,118.9698],[11.6137,118.8556],[11.1896,118.6865],[3.5349,112.3071],[3.4169,111.7869],[3.3974,111.7913],[3.5156,112.3125],[3.5786,112.5215],[3.7326,112.8521],[3.7507,112.8436],[3.5975,112.515],[3.5349,112.3071],[16.2621,111.8134],[16.2602,111.6623],[16.1619,111.5689],[16.2252,111.8161],[16.2621,111.8134],[16.059,112.6126],[16.0432,112.4615],[16.0009,112.4753],[16.059,112.6126],[7.3443,109.464],[7.523,109.9487],[7.5597,109.6531],[7.3443,109.464],[10.3957,116.4888],[10.3091,116.4672],[10.3351,116.6446],[10.3957,116.4888],[20.8055,121.172],[21.6874,121.9094],[21.7003,121.894],[20.8183,121.1567],[20.8055,121.172],[18.0071,119.4737],[19.024,120.0257],[19.0336,120.0081],[18.0166,119.4561],[18.0071,119.4737],[15.0075,119.0722],[16.0439,119.0727],[16.0439,119.0527],[15.0078,119.0522],[15.0075,119.0722],[7.1467,115.5447],[7.9793,116.2505],[7.9922,116.2352],[7.1597,115.5294],[7.1467,115.5447],[6.0127,108.2901],[6.0199,108.3088],[6.0954,108.2796],[6.2275,108.2561],[6.5382,108.2168],[6.9496,108.2188],[7.0739,108.2442],[7.0779,108.2246],[6.9507,108.1988],[6.5376,108.1968],[6.2248,108.2363],[6.091,108.26],[6.0127,108.2901],[11.3689,110.1282],[11.2534,110.0555],[11.2427,110.0725],[11.3595,110.1459],[11.4813,110.207],[11.605,110.259],[11.7836,110.3046],[11.9457,110.3282],[12.1416,110.3342],[12.2404,110.3323],[12.24,110.3123],[12.142,110.3142],[11.948,110.3084],[11.7871,110.2849],[11.6107,110.2398],[11.49,110.189],[11.3689,110.1282],[15.1532,109.8452],[15.1572,109.8648],[15.2339,109.8489],[15.4507,109.7897],[15.6755,109.6901],[15.8368,109.5915],[15.9226,109.532],[16.2073,109.3089],[16.1949,109.2931],[15.911,109.5157],[15.8261,109.5746],[15.6656,109.6726],[15.4447,109.7707],[15.229,109.8295],[15.1532,109.8452],
  ]
  const PI = [0, 268, 277, 286, 291, 296, 302, 308, 312, 317, 322, 331, 340, 345, 349, 353, 357, 362, 367, 372, 377, 390, 407]
  const chinaPolys = PI.map((s, i, a) => P.slice(s, a[i + 1] || P.length)).filter((p) => p.length > 2)
  const smoothP = (poly: number[][]) => {
    const r: number[][] = []
    for (let i = 0; i < poly.length; i++) {
      const a = poly[i], b = poly[(i + 1) % poly.length]
      r.push(a)
      r.push([a[0] + (b[0] - a[0]) * 0.33, a[1] + (b[1] - a[1]) * 0.33])
      r.push([a[0] + (b[0] - a[0]) * 0.66, a[1] + (b[1] - a[1]) * 0.66])
    }
    return r
  }
  for (let i = 0; i < chinaPolys.length; i++) chinaPolys[i] = smoothP(chinaPolys[i])

  let cnMinY = 0, cnMaxY = 0
  const calcBounds = () => {
    let minLat = 90, maxLat = -90
    chinaPolys.forEach((poly) => poly.forEach(([lat]: number[]) => { if (lat < minLat) minLat = lat; if (lat > maxLat) maxLat = lat }))
    const t = proj(maxLat, 103), b = proj(minLat, 103)
    cnMinY = t ? t.y : 0
    cnMaxY = b ? b.y : 0
  }
  calcBounds()

  const randInChina = () => {
    const z = Math.random()
    if (z < 0.25) return { lat: 22 + Math.random() * 7, lng: 110 + Math.random() * 10 }
    if (z < 0.45) return { lat: 30 + Math.random() * 5, lng: 114 + Math.random() * 8 }
    if (z < 0.6) return { lat: 28 + Math.random() * 5, lng: 106 + Math.random() * 8 }
    if (z < 0.75) return { lat: 36 + Math.random() * 6, lng: 108 + Math.random() * 10 }
    if (z < 0.88) return { lat: 24 + Math.random() * 5, lng: 100 + Math.random() * 6 }
    return { lat: 38 + Math.random() * 4, lng: 80 + Math.random() * 8 }
  }

  function draw(t: number) {
    const time = t * 0.001
    ctx.clearRect(0, 0, W, H)
    const cx = W / 2, cy = H / 2 + 10, ps = Math.min(W, H) * 0.95, px = cx, py = H - 25
    const A = colors.accent, W2 = colors.warning

    // 投影仪底座
    const bg = ctx.createRadialGradient(px, py, 0, px, py, 35)
    bg.addColorStop(0, rgba(A, 0.15 + 0.05 * Math.sin(time * 0.5)))
    bg.addColorStop(0.4, rgba(A, 0.06))
    bg.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.fillStyle = bg
    ctx.fillRect(px - 35, py - 35, 70, 45)
    ctx.strokeStyle = rgba(A, 0.12 + 0.04 * Math.sin(time * 0.7))
    ctx.lineWidth = 1.5
    ctx.beginPath(); ctx.arc(px, py, 12, 0, 6.28); ctx.stroke()
    ctx.strokeStyle = rgba(A, 0.08); ctx.lineWidth = 0.8
    ctx.beginPath(); ctx.arc(px, py, 18, 0, 6.28); ctx.stroke()

    // 线性光束
    const cnRange = (cnMaxY - cnMinY) / 2 + 20
    const cnCenter = (cnMaxY + cnMinY) / 2
    const scanY = cnCenter + Math.sin(time * 0.35) * cnRange
    const beamTop = Math.max(cnMinY - 30, Math.min(cnMaxY, scanY))
    ctx.save(); ctx.beginPath(); ctx.moveTo(px - 4, py); ctx.lineTo(px + 4, py)
    ctx.lineTo(cx + ps * 0.25, beamTop); ctx.lineTo(cx - ps * 0.25, beamTop); ctx.closePath()
    const beamGrad = ctx.createLinearGradient(px, py, cx, beamTop)
    beamGrad.addColorStop(0, rgba(A, 0.12 + 0.03 * Math.sin(time * 0.4)))
    beamGrad.addColorStop(0.2, rgba(A, 0.07))
    beamGrad.addColorStop(0.4, rgba(A, 0.04))
    beamGrad.addColorStop(0.6, rgba(A, 0.02))
    beamGrad.addColorStop(0.8, rgba(A, 0.008))
    beamGrad.addColorStop(1, 'rgba(0,0,0,0)')
    ctx.fillStyle = beamGrad; ctx.fill(); ctx.restore()

    // 经纬网格
    ctx.strokeStyle = rgba(A, 0.18); ctx.lineWidth = 0.8
    ctx.beginPath(); ctx.arc(cx, cy, ps, 0, 6.28); ctx.stroke()
    ctx.strokeStyle = rgba(A, 0.22); ctx.lineWidth = 0.8
    for (let lng = 70; lng <= 140; lng += 5) {
      const pts: any[] = []; let ok = true
      for (let lat = 0; lat <= 60; lat += 1) { const p = proj(lat, lng); if (!p) { ok = false; break } pts.push(p) }
      if (!ok || pts.length < 2) continue
      ctx.beginPath(); pts.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y))); ctx.stroke()
    }
    for (let lat = 0; lat <= 60; lat += 5) {
      const pts: any[] = []; let ok = true
      for (let lng = 65; lng <= 145; lng += 1) { const p = proj(lat, lng); if (!p) { ok = false; break } pts.push(p) }
      if (!ok || pts.length < 2) continue
      ctx.beginPath(); pts.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y))); ctx.stroke()
    }

    // 中国轮廓
    chinaPolys.forEach((poly) => {
      const pts: any[] = []; let ok = true
      for (const p of poly) { const gp = proj(p[0], p[1]); if (!gp) { ok = false; break } pts.push(gp) }
      if (!ok || pts.length < 3) return
      ctx.beginPath(); pts.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y))); ctx.closePath()
      ctx.save(); ctx.shadowColor = rgba(A, 0.12); ctx.shadowBlur = 50
      ctx.lineJoin = 'round'; ctx.lineCap = 'round'; ctx.strokeStyle = rgba(A, 0.08); ctx.lineWidth = 4; ctx.stroke(); ctx.restore()
      ctx.save(); ctx.shadowColor = rgba(A, 0.2); ctx.shadowBlur = 20
      ctx.lineJoin = 'round'; ctx.lineCap = 'round'; ctx.strokeStyle = rgba(A, 0.3); ctx.lineWidth = 1.5; ctx.stroke(); ctx.restore()
      ctx.lineJoin = 'round'; ctx.lineCap = 'round'; ctx.strokeStyle = rgba(A, 0.5); ctx.lineWidth = 0.6; ctx.stroke()
    })

    // 扫描线
    ctx.save(); ctx.beginPath(); ctx.arc(cx, cy, ps, 0, 6.28); ctx.clip()
    ctx.strokeStyle = rgba(A, 0.05 + 0.02 * Math.sin(time * 0.3)); ctx.lineWidth = 1.5
    ctx.beginPath(); ctx.moveTo(0, scanY); ctx.lineTo(W, scanY); ctx.stroke(); ctx.restore()

    // 引导线箭头
    while (arrows.length < 2) {
      const a = randInChina(), b = randInChina()
      if (Math.abs(a.lat - b.lat) + Math.abs(a.lng - b.lng) < 8) continue
      arrows.push({ from: a, to: b, prog: 0, spd: 0.0015 + Math.random() * 0.002, delay: Math.random() * 60, linger: 0 })
    }
    for (let i = arrows.length - 1; i >= 0; i--) {
      const arr = arrows[i]
      if (arr.delay > 0) { arr.delay--; continue }
      if (arr.linger > 0) {
        arr.linger--
        if (arr.linger <= 0) { arrows.splice(i, 1); continue }
        const pp2 = proj(arr.to.lat, arr.to.lng)
        if (pp2) {
          const fa = arr.linger / 30
          const fg = ctx.createRadialGradient(pp2.x, pp2.y, 0, pp2.x, pp2.y, 6)
          fg.addColorStop(0, rgba(A, 0.15 * fa)); fg.addColorStop(1, 'transparent')
          ctx.beginPath(); ctx.arc(pp2.x, pp2.y, 6, 0, 6.28); ctx.fillStyle = fg; ctx.fill()
          ctx.beginPath(); ctx.arc(pp2.x, pp2.y, 2, 0, 6.28); ctx.fillStyle = rgba(W2, 0.6 * fa); ctx.fill()
        }
        continue
      }
      arr.prog += arr.spd
      if (arr.prog > 1) { arr.linger = 30; continue }
      const p1 = proj(arr.from.lat, arr.from.lng), p2 = proj(arr.to.lat, arr.to.lng)
      if (!p1 || !p2) continue
      const p = arr.prog
      const sa = 1 - p * 0.7
      if (sa > 0) {
        const sg = ctx.createRadialGradient(p1.x, p1.y, 0, p1.x, p1.y, 5)
        sg.addColorStop(0, rgba(A, 0.1 * sa)); sg.addColorStop(1, 'transparent')
        ctx.beginPath(); ctx.arc(p1.x, p1.y, 5, 0, 6.28); ctx.fillStyle = sg; ctx.fill()
        ctx.beginPath(); ctx.arc(p1.x, p1.y, 1.5, 0, 6.28); ctx.fillStyle = rgba(W2, 0.5 * sa); ctx.fill()
      }
      const cx2 = (p1.x + p2.x) / 2, cy2 = (p1.y + p2.y) / 2 - Math.abs(p1.x - p2.x) * 0.15 - 20
      const segs: any[] = []; const dc = Math.floor(p * 120)
      for (let j = 0; j <= dc && j <= 120; j++) { const tt = j / 120; segs.push({ x: (1 - tt) * (1 - tt) * p1.x + 2 * (1 - tt) * tt * cx2 + tt * tt * p2.x, y: (1 - tt) * (1 - tt) * p1.y + 2 * (1 - tt) * tt * cy2 + tt * tt * p2.y }) }
      if (segs.length > 1) {
        ctx.beginPath(); ctx.moveTo(segs[0].x, segs[0].y)
        for (let j = 1; j < segs.length; j++) ctx.lineTo(segs[j].x, segs[j].y)
        ctx.lineJoin = 'round'; ctx.lineCap = 'round'; ctx.strokeStyle = rgba(W2, 0.15 + 0.1 * Math.sin(p * Math.PI)); ctx.lineWidth = 1.2; ctx.stroke()
      }
      if (segs.length >= 2) {
        const last = segs[segs.length - 1]; const prev = segs.length >= 3 ? segs[segs.length - 3] : segs[0]
        const a2 = Math.atan2(last.y - prev.y, last.x - prev.x)
        ctx.beginPath(); ctx.moveTo(last.x, last.y); ctx.lineTo(last.x - 6 * Math.cos(a2 - 0.5), last.y - 6 * Math.sin(a2 - 0.5))
        ctx.moveTo(last.x, last.y); ctx.lineTo(last.x - 6 * Math.cos(a2 + 0.5), last.y - 6 * Math.sin(a2 + 0.5))
        ctx.strokeStyle = rgba(A, 0.2 + 0.15 * Math.sin(p * Math.PI)); ctx.lineWidth = 1.5; ctx.stroke()
        const ag = ctx.createRadialGradient(last.x, last.y, 0, last.x, last.y, 6)
        ag.addColorStop(0, rgba(A, 0.1 * Math.sin(p * Math.PI))); ag.addColorStop(1, 'transparent')
        ctx.beginPath(); ctx.arc(last.x, last.y, 6, 0, 6.28); ctx.fillStyle = ag; ctx.fill()
      }
      if (p > 0.7) {
        const fa = (p - 0.7) / 0.3
        const fg = ctx.createRadialGradient(p2.x, p2.y, 0, p2.x, p2.y, 5)
        fg.addColorStop(0, rgba(A, 0.1 * fa)); fg.addColorStop(1, 'transparent')
        ctx.beginPath(); ctx.arc(p2.x, p2.y, 5, 0, 6.28); ctx.fillStyle = fg; ctx.fill()
        ctx.beginPath(); ctx.arc(p2.x, p2.y, 1.5 * fa, 0, 6.28); ctx.fillStyle = rgba(W2, 0.5 * fa); ctx.fill()
      }
    }

    ctx.fillStyle = rgba(colors.tertiary, 0.5); ctx.font = '10px ui-monospace, monospace'
    ctx.textAlign = 'left'; ctx.textBaseline = 'top'
    ctx.fillText('// CHINA · 智配寻源网络', 14, 14)

    if (!paused.value && !reduced.value) {
      animId = requestAnimationFrame(draw)
    }
  }

  // 主题切换：重读令牌颜色并重绘
  themeObserver = new MutationObserver(() => {
    readColors()
    if (paused.value || reduced.value) draw(performance.now())
  })
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })

  drawFn = draw
  if (reduced.value) {
    draw(0) // 静态一帧
  } else {
    animId = requestAnimationFrame(draw)
  }
})

function togglePause() {
  paused.value = !paused.value
  // 恢复播放：手动触发一帧，draw 末尾会自动续接 rAF 循环
  if (!paused.value && !reduced.value) {
    cancelAnimationFrame(animId)
    drawFn?.(performance.now())
  }
}

onUnmounted(() => {
  cancelAnimationFrame(animId)
  ro?.disconnect()
  themeObserver?.disconnect()
})
</script>

<template>
  <div class="holo-map">
    <canvas ref="canvasRef" class="holo-map__canvas" aria-hidden="true" />
    <button
      v-if="!reduced"
      type="button"
      class="holo-map__pause"
      :aria-label="paused ? '播放地图动画' : '暂停地图动画'"
      @click="togglePause"
    >{{ paused ? '▶' : '❚❚' }}</button>
  </div>
</template>

<style scoped>
.holo-map {
  position: absolute;
  inset: 0;
  overflow: hidden;
}
.holo-map__canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
}
.holo-map__pause {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  z-index: 2;
  width: var(--space-5);
  height: var(--space-5);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  color: var(--text-tertiary);
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: color var(--transition-fast), border-color var(--transition-fast);
}
.holo-map__pause:hover {
  color: var(--text-primary);
  border-color: var(--accent-border);
}
</style>
