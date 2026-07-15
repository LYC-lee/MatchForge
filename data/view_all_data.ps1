# view_all_data.ps1
# 在 D:\MatchForge\data 目录下运行: powershell -ExecutionPolicy Bypass -File view_all_data.ps1

Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  MatchForge P4 数据查看工具" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# ---- 1. 种子供应商 ----
Write-Host ""
Write-Host "========== 1. 种子供应商 suppliers.json ==========" -ForegroundColor Yellow
$data = Get-Content "suppliers\suppliers.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$productCount = 0
foreach ($s in $data) { $productCount += $s.products.Count }
Write-Host "供应商总数: $($data.Count) 家"
Write-Host "产品总数: $productCount 条"
Write-Host ""
Write-Host "--- 地区分布 ---"
$data | Group-Object location | Sort-Object Count -Descending | ForEach-Object { Write-Host "  $($_.Name): $($_.Count) 家" }
Write-Host ""
Write-Host "--- 品类分布 ---"
$allProducts = $data | ForEach-Object { $_.products }
$allProducts | Group-Object category | Sort-Object Count -Descending | ForEach-Object { Write-Host "  $($_.Name): $($_.Count) 条" }
Write-Host ""
Write-Host "--- 前5家供应商 ---"
$data | Select-Object -First 5 | ForEach-Object {
    Write-Host "  $($_.id). $($_.name) ($($_.location)) 主营:$($_.main_category) 评分:$($_.rating) 产品:$($_.products.Count)条" -ForegroundColor Green
    $_.products | Select-Object -First 2 | ForEach-Object {
        Write-Host "      $($_.part_number) ($($_.brand)) $($_.category)"
    }
}

# ---- 2. 替代料交叉引用 ----
Write-Host ""
Write-Host "========== 2. 替代料交叉引用 alternatives.json ==========" -ForegroundColor Yellow
$adata = Get-Content "alternatives\alternatives.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$groups = $adata.groups
$eqCount = 0
foreach ($g in $groups) { $eqCount += $g.equivalences.Count }
Write-Host "替代料组数: $($groups.Count) 组"
Write-Host "替代关系数: $eqCount 条"
Write-Host ""
Write-Host "--- 品类分布 ---"
$groups | Group-Object category | Sort-Object Count -Descending | ForEach-Object { Write-Host "  $($_.Name): $($_.Count) 组" }
Write-Host ""
Write-Host "--- 前5组示例 ---"
$groups | Select-Object -First 5 | ForEach-Object {
    Write-Host "  组$($_.group_id): $($_.category) - $($_.spec) ($($_.parts.Count)个料号, $($_.equivalences.Count)条关系)" -ForegroundColor Green
    $_.parts | Select-Object -First 3 | ForEach-Object {
        Write-Host "      $($_.part_number) ($($_.brand))"
    }
}

# ---- 3. 标准字典 ----
Write-Host ""
Write-Host "========== 3. 标准字典 dictionary.json ==========" -ForegroundColor Yellow
$ddata = Get-Content "dictionary\dictionary.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$items = $ddata.items
Write-Host "字典条目数: $($items.Count) 条"
Write-Host ""
Write-Host "--- 品类分布 ---"
$items | Group-Object category | Sort-Object Count -Descending | ForEach-Object { Write-Host "  $($_.Name): $($_.Count) 条" }
Write-Host ""
Write-Host "--- 前5条示例 ---"
$items | Select-Object -First 5 | ForEach-Object {
    Write-Host "  $($_.std_code)" -ForegroundColor Green
    Write-Host "    品类: $($_.category)"
    Write-Host "    标准: $($_.standard)"
    Write-Host "    描述: $($_.description)"
}

# ---- 4. 其他文件 ----
Write-Host ""
Write-Host "========== 4. 其他文件 ==========" -ForegroundColor Yellow
Write-Host "  mysql_schema.sql:      $(Get-Content mysql_schema.sql | Measure-Object -Line).Lines 行"
Write-Host "  init_all.py:           $(Get-Content init_all.py | Measure-Object -Line).Lines 行"
Write-Host "  milvus_collections.py: $(Get-Content milvus_collections.py | Measure-Object -Line).Lines 行"
Write-Host "  milvus_seed_data.py:   $(Get-Content milvus_seed_data.py | Measure-Object -Line).Lines 行"
Write-Host "  knowledge_base_docs.py:$(Get-Content knowledge_base_docs.py | Measure-Object -Line).Lines 行"

Write-Host ""
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  数据查看完毕!" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan
