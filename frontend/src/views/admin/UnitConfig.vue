<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import {
  getGlobalConfig,
  getModelConfig,
  getUnitConfigs,
  updateGlobalConfig,
  updateModelConfig,
  updateUnitConfig,
} from '../../api/admin'

// 6 个优化单元配置（编辑副本，保存时提交）
const units = ref([])
const loading = ref(false)
const savingUnit = ref(0)     // 正在保存的单元号
const activePanels = ref([])  // 折叠面板展开状态

// 六份调用指令：s1/s2/s3（通用版）+ g1/g2/g3（竖屏 9:16 优化版，OpenRouter 专用）
const instructions = reactive({ s1: '', s2: '', s3: '', g1: '', g2: '', g3: '' })
const savingInstruction = ref('')

// LLM 模型配置（多平台 OpenAI 兼容）
const modelForm = reactive({
  platform: 'openai',
  model: '',
  model_label: '',
  base_url: '',
  api_key: '',
  reasoning_enabled: false,
})
const platforms = ref([])        // 平台预设列表
const modelMasked = ref('')       // 已保存 Key 的掩码（不明文展示）
const hasApiKey = ref(false)
const savingModel = ref(false)

const modelWarning = computed(() => {
  if (!hasApiKey.value && !modelForm.api_key) {
    return '尚未配置 API Key，调用模型将失败，请在下方填写 Key 后保存'
  }
  return ''
})

// 模型名占位提示（仅作参考，不自动填充，由用户自行填写）
const modelPlaceholder = computed(() => {
  const p = platforms.value.find((x) => x.key === modelForm.platform)
  return p?.default_model ? `例如 ${p.default_model}` : '请填写模型名称'
})

// 切换平台时自动填充接口地址与推理开关；模型名不设默认，由用户自行填写
function onPlatformChange(key) {
  const p = platforms.value.find((x) => x.key === key)
  if (p) {
    modelForm.base_url = p.base_url
    modelForm.reasoning_enabled = p.reasoning
  }
}

// 模型命名默认值：从模型名提取供应商品牌
// google/gemini-3.7-flash → gemini、gpt-4o-mini → gpt、deepseek-chat → deepseek
function extractModelLabel(model) {
  if (!model) return ''
  const cleaned = String(model).trim().replace(/：/g, ':')
  const seg = cleaned.includes('/') ? cleaned.split('/').pop() : cleaned
  const m = seg.match(/^[a-zA-Z]+/)
  return m ? m[0].toLowerCase() : ''
}

// 用户修改模型名后，自动回填模型命名（默认供应商）
function onModelChange() {
  modelForm.model_label = extractModelLabel(modelForm.model)
}

async function refresh() {
  loading.value = true
  try {
    units.value = await getUnitConfigs()
    const g = await getGlobalConfig()
    instructions.s1 = g.global_instruction_s1
    instructions.s2 = g.global_instruction_s2
    instructions.s3 = g.global_instruction_s3
    instructions.g1 = g.global_instruction_g1
    instructions.g2 = g.global_instruction_g2
    instructions.g3 = g.global_instruction_g3

    const m = await getModelConfig()
    modelForm.platform = m.platform
    modelForm.model = m.model
    modelForm.model_label = m.model_label
    modelForm.base_url = m.base_url
    modelForm.reasoning_enabled = m.reasoning_enabled
    modelForm.api_key = ''
    modelMasked.value = m.api_key_masked
    hasApiKey.value = m.has_api_key
    platforms.value = m.platforms || []
  } finally {
    loading.value = false
  }
}

async function saveUnit(unit) {
  savingUnit.value = unit.unit_no
  try {
    await updateUnitConfig(unit.unit_no, {
      name: unit.name,
      default_template: unit.default_template,
      unit_instruction: unit.unit_instruction,
    })
    ElMessage.success(`单元 ${unit.unit_no} 配置已保存，用户端立即生效`)
  } finally {
    savingUnit.value = 0
  }
}

async function saveInstruction(key) {
  if (!instructions[key].trim()) {
    ElMessage.warning('指令内容不能为空')
    return
  }
  savingInstruction.value = key
  try {
    await updateGlobalConfig({
      global_instruction_s1: instructions.s1,
      global_instruction_s2: instructions.s2,
      global_instruction_s3: instructions.s3,
      global_instruction_g1: instructions.g1,
      global_instruction_g2: instructions.g2,
      global_instruction_g3: instructions.g3,
    })
    ElMessage.success(`指令 ${key.toUpperCase()} 已保存，之后每轮调用立即生效`)
  } finally {
    savingInstruction.value = ''
  }
}

async function saveModel() {
  if (!modelForm.model.trim()) {
    ElMessage.warning('模型名不能为空')
    return
  }
  savingModel.value = true
  try {
    const resp = await updateModelConfig({
      platform: modelForm.platform,
      model: modelForm.model.trim(),
      model_label: modelForm.model_label.trim(),
      base_url: modelForm.base_url.trim(),
      api_key: modelForm.api_key.trim(), // 留空表示不修改
      reasoning_enabled: modelForm.reasoning_enabled,
    })
    modelForm.api_key = ''
    modelMasked.value = resp.api_key_masked
    hasApiKey.value = resp.has_api_key
    ElMessage.success('模型配置已保存并立即生效（无需重启）')
  } finally {
    savingModel.value = false
  }
}

onMounted(refresh)
</script>

<template>
  <div v-loading="loading" class="config-page">
    <!-- LLM 模型配置（多平台 OpenAI 兼容） -->
    <el-card shadow="never" class="config-card">
      <template #header>
        <div class="card-header">
          <div>
            <span>LLM 模型配置</span>
            <div class="header-tip">
              支持 OpenAI 官方 / OpenRouter / Kimi / 智谱 / 通义等 OpenAI 兼容平台；
              模型名、模型地址、API Key 均可在管理端修改；API Key 不明文展示；保存后立即生效
            </div>
          </div>
        </div>
      </template>
      <el-form label-width="110px">
        <el-form-item label="模型平台">
          <el-select v-model="modelForm.platform" style="width: 320px" @change="onPlatformChange">
            <el-option
              v-for="p in platforms"
              :key="p.key"
              :value="p.key"
              :label="p.label"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="模型名称">
          <el-input
            v-model="modelForm.model"
            :placeholder="modelPlaceholder"
            style="width: 320px"
            @change="onModelChange"
          />
        </el-form-item>
        <el-form-item label="模型地址">
          <el-input
            v-model="modelForm.base_url"
            placeholder="https://api.openai.com/v1"
            style="width: 460px"
          />
        </el-form-item>
        <el-form-item label="模型命名">
          <el-input
            v-model="modelForm.model_label"
            maxlength="50"
            placeholder="留空自动按模型名提取，如 gpt / gemini / deepseek"
            style="width: 320px"
          />
          <span class="reasoning-tip">默认提取供应商品牌，可自定义；用于审计与工作台显示</span>
        </el-form-item>
        <el-form-item label="推理模型">
          <el-switch v-model="modelForm.reasoning_enabled" />
          <span class="reasoning-tip">推理模型（如 gpt-oss）需开启，调用时附带 reasoning 参数</span>
        </el-form-item>
        <el-form-item label="API Key">
          <el-input
            v-model="modelForm.api_key"
            type="password"
            show-password
            :placeholder="hasApiKey ? `已配置：${modelMasked}（留空表示不修改）` : '请输入 API Key'"
            style="width: 460px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="savingModel" @click="saveModel">
            保存模型配置
          </el-button>
          <el-alert
            v-if="modelWarning"
            type="warning"
            :closable="false"
            show-icon
            :title="modelWarning"
            class="model-warning"
          />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 六份调用指令 s1/s2/s3（通用版）+ g1/g2/g3（竖屏优化版） -->
    <el-card shadow="never" class="config-card">
      <template #header>
        <div class="card-header">
          <div>
            <span>调用指令配置</span>
            <div class="header-tip">
              s1/s2/s3 通用版（ai.klinkw.com 等模型使用）· g1/g2/g3 竖屏 9:16 优化版（OpenRouter 模型使用，自动切换）
            </div>
          </div>
        </div>
      </template>

      <el-collapse v-model="activePanels">
        <el-collapse-item name="s1">
          <template #title><b>指令 s1 · 单元 1、2</b></template>
          <el-input v-model="instructions.s1" type="textarea" :rows="12" maxlength="20000" show-word-limit />
          <el-button
            type="primary"
            class="ins-save"
            :loading="savingInstruction === 's1'"
            @click="saveInstruction('s1')"
          >
            保存指令 s1
          </el-button>
        </el-collapse-item>

        <el-collapse-item name="s2">
          <template #title><b>指令 s2 · 后续对话统一调用指令（单元 3-6）</b></template>
          <el-input v-model="instructions.s2" type="textarea" :rows="12" maxlength="20000" show-word-limit />
          <el-button
            type="primary"
            class="ins-save"
            :loading="savingInstruction === 's2'"
            @click="saveInstruction('s2')"
          >
            保存指令 s2
          </el-button>
        </el-collapse-item>

        <el-collapse-item name="s3">
          <template #title><b>指令 s3 · 修改提示词（修改对话框流程）</b></template>
          <el-input v-model="instructions.s3" type="textarea" :rows="12" maxlength="20000" show-word-limit />
          <el-button
            type="primary"
            class="ins-save"
            :loading="savingInstruction === 's3'"
            @click="saveInstruction('s3')"
          >
            保存指令 s3
          </el-button>
        </el-collapse-item>

        <el-collapse-item name="g1">
          <template #title><b>指令 g1 · 单元 1、2 竖屏版</b></template>
          <el-input v-model="instructions.g1" type="textarea" :rows="12" maxlength="20000" show-word-limit />
          <el-button
            type="primary"
            class="ins-save"
            :loading="savingInstruction === 'g1'"
            @click="saveInstruction('g1')"
          >
            保存指令 g1
          </el-button>
        </el-collapse-item>

        <el-collapse-item name="g2">
          <template #title><b>指令 g2 · 后续对话统一调用指令（单元 3-6）竖屏版</b></template>
          <el-input v-model="instructions.g2" type="textarea" :rows="12" maxlength="20000" show-word-limit />
          <el-button
            type="primary"
            class="ins-save"
            :loading="savingInstruction === 'g2'"
            @click="saveInstruction('g2')"
          >
            保存指令 g2
          </el-button>
        </el-collapse-item>

        <el-collapse-item name="g3">
          <template #title><b>指令 g3 · 修改提示词（修改对话框流程）竖屏版</b></template>
          <el-input v-model="instructions.g3" type="textarea" :rows="12" maxlength="20000" show-word-limit />
          <el-button
            type="primary"
            class="ins-save"
            :loading="savingInstruction === 'g3'"
            @click="saveInstruction('g3')"
          >
            保存指令 g3
          </el-button>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <!-- 6 个优化单元配置 -->
    <el-card shadow="never" class="config-card">
      <template #header>
        <div class="card-header">
          <div>
            <span>6 组优化单元配置</span>
            <div class="header-tip">
              每个单元包含「待优化提示词输入 → 优化结果输出 → 自定义指令面板」；默认模板用于单元 1 的种子模板
              及单元 i(≥2) 无链式历史时的回退模板
            </div>
          </div>
        </div>
      </template>

      <el-collapse>
        <el-collapse-item v-for="unit in units" :key="unit.unit_no" :name="`u${unit.unit_no}`">
          <template #title>
            <b>单元 {{ unit.unit_no }}</b>
          </template>

          <el-form label-position="top">
            <el-form-item label="单元名称">
              <el-input v-model="unit.name" maxlength="100" />
            </el-form-item>
            <el-form-item label="默认模板（种子 / 回退基础模板）">
              <el-input v-model="unit.default_template" type="textarea" :rows="4" maxlength="20000" show-word-limit />
            </el-form-item>
            <el-form-item label="单元自定义指令（展示在用户端的指令面板中）">
              <el-input v-model="unit.unit_instruction" type="textarea" :rows="4" maxlength="20000" show-word-limit />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="savingUnit === unit.unit_no" @click="saveUnit(unit)">
                保存单元 {{ unit.unit_no }}
              </el-button>
            </el-form-item>
          </el-form>
        </el-collapse-item>
      </el-collapse>
    </el-card>
  </div>
</template>

<style scoped>
.config-page {
  max-width: 900px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.header-tip {
  font-size: 12px;
  font-weight: 400;
  color: #909399;
  margin-top: 4px;
}

.ins-save {
  margin-top: 12px;
}

.model-warning {
  margin-left: 12px;
  display: inline-flex;
}

.provider-fixed {
  font-weight: 600;
  color: #303133;
}

.reasoning-tip {
  margin-left: 12px;
  font-size: 12px;
  color: #909399;
}
</style>
