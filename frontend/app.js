const { createApp } = Vue;

const STAGE_LABELS = {
  idea: "创意",
  setting: "全书设定",
  outline: "全书大纲",
  writing: "写作中",
  completed: "已完结",
};

const VOLUME_STAGE_LABELS = {
  volume_outline: "待卷大纲",
  volume_plan: "待卷规划",
  writing: "写作中",
  volume_completed: "卷已完成",
};

const VOLUME_STATUS_LABELS = {
  draft: "草稿",
  writing: "写作中",
  completed: "已完成",
};

const STATUS_LABELS = {
  generating: "生成中",
  draft: "草稿",
  confirmed: "已确认",
  failed: "失败",
};

createApp({
  data() {
    return {
      view: "list",
      projects: [],
      project: null,
      activeTab: "setting",
      tabs: [
        { key: "setting", label: "设定" },
        { key: "outline", label: "全书大纲" },
        { key: "volumes", label: "卷" },
        { key: "tracking", label: "追踪" },
      ],
      // 全局设定 / 全书大纲编辑
      settingText: "",
      outlineText: "",
      // 卷相关
      selectedVolumeId: null,
      currentVolume: null,
      volumeTab: "outline",
      volumeTabs: [
        { key: "outline", label: "卷大纲" },
        { key: "plan", label: "卷规划" },
        { key: "chapters", label: "章节" },
      ],
      volumeOutlineText: "",
      planChapters: [],
      currentChapter: null,
      chapterPage: 1,
      chapterPageSize: 50,
      // 新建项目
      newPremise: "",
      newTitle: "",
      creating: false,
      creatingVolume: false,
      // 灵感创意
      ideas: [],
      showIdeas: false,
      ideasLoading: false,
      // 状态
      error: "",
      streaming: false,
      liveContent: "",
      generatingSetting: false,
      generatingOutline: false,
      generatingVolumeOutline: false,
      generatingVolumePlan: false,
      saving: false,
    };
  },
  mounted() {
    this.loadProjects();
  },
  methods: {
    stageLabel(s) {
      return STAGE_LABELS[s] || s;
    },
    volumeStageLabel(s) {
      return VOLUME_STAGE_LABELS[s] || s;
    },
    volumeStatusLabel(s) {
      return VOLUME_STATUS_LABELS[s] || s;
    },
    chapterStatus(s) {
      return STATUS_LABELS[s] || s;
    },
    pretty(obj) {
      return JSON.stringify(obj, null, 2);
    },
    isCurrentVolume(v) {
      return this.project && v && v.id === this.project.current_volume_id;
    },
    currentVolumeId() {
      return this.selectedVolumeId || (this.project && this.project.current_volume_id) || null;
    },

    async api(url, opts = {}) {
      const resp = await fetch(url, opts);
      if (!resp.ok) {
        let detail = resp.statusText;
        try {
          const j = await resp.json();
          detail = j.detail || detail;
        } catch (e) {}
        throw new Error(detail);
      }
      return resp.json();
    },

    // ---- 项目列表 ----
    async loadProjects() {
      try {
        this.projects = await this.api("/api/projects");
      } catch (e) {
        this.error = e.message;
      }
    },

    async createProject() {
      if (!this.newPremise.trim()) {
        this.error = "请输入创意";
        return;
      }
      this.error = "";
      this.creating = true;
      try {
        const p = await this.api("/api/projects", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            premise: this.newPremise.trim(),
            title: this.newTitle.trim() || null,
          }),
        });
        this.newPremise = "";
        this.newTitle = "";
        await this.loadProjects();
        await this.openProject(p.id);
      } catch (e) {
        this.error = e.message;
      } finally {
        this.creating = false;
      }
    },

    async openProject(id) {
      this.error = "";
      try {
        this.project = await this.api(`/api/projects/${id}`);
        this.view = "project";
        this.activeTab = "setting";
        this.currentVolume = null;
        this.currentChapter = null;
        this.syncFromProject();
        const vid = this.currentVolumeId();
        if (vid) await this.loadVolumeDetail(vid);
      } catch (e) {
        this.error = e.message;
      }
    },

    // ---- 灵感创意 ----
    async generateIdeas() {
      this.error = "";
      this.ideasLoading = true;
      this.showIdeas = true;
      this.ideas = [];
      try {
        const data = await this.api("/api/ideas/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ count: 5 }),
        });
        this.ideas = data.ideas || [];
      } catch (e) {
        this.error = e.message;
        this.ideas = [];
      } finally {
        this.ideasLoading = false;
      }
    },

    useIdea(idea) {
      this.newPremise = idea.idea || "";
      this.newTitle = idea.title || "";
      this.closeIdeas();
    },

    closeIdeas() {
      this.showIdeas = false;
      this.ideas = [];
    },

    backToList() {
      this.view = "list";
      this.project = null;
      this.currentVolume = null;
      this.currentChapter = null;
      this.error = "";
      this.loadProjects();
    },

    async refreshProject() {
      this.project = await this.api(`/api/projects/${this.project.id}`);
      this.syncFromProject();
      if (this.currentVolume) {
        const vid = this.currentVolume.id;
        if (this.project.volumes.some((v) => v.id === vid)) {
          await this.loadVolumeDetail(vid);
        } else {
          const nv = this.currentVolumeId();
          if (nv) await this.loadVolumeDetail(nv);
        }
      }
    },

    syncFromProject() {
      this.settingText = this.project.setting ? this.pretty(this.project.setting) : "";
      this.outlineText = this.project.outline ? this.pretty(this.project.outline) : "";
      if (!this.selectedVolumeId && this.project.volumes.length) {
        this.selectedVolumeId = this.project.current_volume_id || this.project.volumes[0].id;
      }
    },

    setTab(t) {
      this.activeTab = t;
    },

    // ---- 设定 ----
    async generateSetting() {
      this.error = "";
      this.generatingSetting = true;
      try {
        await this.api(`/api/projects/${this.project.id}/settings`, { method: "POST" });
        await this.refreshProject();
      } catch (e) {
        this.error = e.message;
      } finally {
        this.generatingSetting = false;
      }
    },

    async saveSetting() {
      await this.saveGlobalJson("settings", "设定");
    },

    // ---- 全书大纲 ----
    async generateOutline() {
      this.error = "";
      this.generatingOutline = true;
      try {
        await this.api(`/api/projects/${this.project.id}/outline`, { method: "POST" });
        await this.refreshProject();
        this.activeTab = "volumes";
      } catch (e) {
        this.error = e.message;
      } finally {
        this.generatingOutline = false;
      }
    },

    async saveOutline() {
      await this.saveGlobalJson("outline", "全书大纲");
    },

    async saveGlobalJson(kind, label) {
      this.error = "";
      this.saving = true;
      try {
        const text = kind === "settings" ? this.settingText : this.outlineText;
        let content;
        try {
          content = JSON.parse(text);
        } catch (e) {
          throw new Error(`${label} JSON 格式错误`);
        }
        await this.api(`/api/projects/${this.project.id}/${kind}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content }),
        });
        await this.refreshProject();
      } catch (e) {
        this.error = e.message;
      } finally {
        this.saving = false;
      }
    },

    // ---- 卷 ----
    async loadVolumeDetail(id) {
      try {
        this.currentVolume = await this.api(`/api/volumes/${id}`);
        this.selectedVolumeId = id;
        this.syncVolumeEditors();
        this.chapterPage = 1;
      } catch (e) {
        this.error = e.message;
      }
    },

    async selectVolume(id) {
      if (id === this.selectedVolumeId && this.currentVolume) return;
      this.currentChapter = null;
      await this.loadVolumeDetail(id);
    },

    async createVolume() {
      this.error = "";
      this.creatingVolume = true;
      try {
        const v = await this.api(`/api/projects/${this.project.id}/volumes`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        });
        await this.refreshProject();
        await this.loadVolumeDetail(v.id);
      } catch (e) {
        this.error = e.message;
      } finally {
        this.creatingVolume = false;
      }
    },

    setVolumeTab(t) {
      this.volumeTab = t;
    },

    syncVolumeEditors() {
      const v = this.currentVolume;
      if (!v) return;
      this.volumeOutlineText = v.outline ? this.pretty(v.outline) : "";
      const plan = v.chapter_plan;
      this.planChapters =
        plan && Array.isArray(plan.chapters)
          ? plan.chapters.map((c) => ({
              number: c.number || 0,
              title: c.title || "",
              summary: c.summary || "",
            }))
          : [];
      if (this.currentChapter) {
        const fresh = (v.chapters || []).find((c) => c.id === this.currentChapter.id);
        if (fresh) this.currentChapter = { ...fresh };
      }
    },

    async generateVolumeOutline() {
      this.error = "";
      this.generatingVolumeOutline = true;
      try {
        await this.api(`/api/volumes/${this.currentVolume.id}/outline`, { method: "POST" });
        await this.refreshProject();
      } catch (e) {
        this.error = e.message;
      } finally {
        this.generatingVolumeOutline = false;
      }
    },

    async saveVolumeOutline() {
      this.error = "";
      this.saving = true;
      try {
        let content;
        try {
          content = JSON.parse(this.volumeOutlineText);
        } catch (e) {
          throw new Error("卷大纲 JSON 格式错误");
        }
        await this.api(`/api/volumes/${this.currentVolume.id}/outline`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content }),
        });
        await this.refreshProject();
      } catch (e) {
        this.error = e.message;
      } finally {
        this.saving = false;
      }
    },

    async generateVolumePlan() {
      this.error = "";
      this.generatingVolumePlan = true;
      try {
        await this.api(`/api/volumes/${this.currentVolume.id}/chapter-plan`, { method: "POST" });
        await this.refreshProject();
      } catch (e) {
        this.error = e.message;
      } finally {
        this.generatingVolumePlan = false;
      }
    },

    addPlanChapter() {
      this.planChapters.push({
        number: this.planChapters.length + 1,
        title: "",
        summary: "",
      });
    },

    async saveVolumePlan() {
      this.error = "";
      this.saving = true;
      try {
        const chapters = this.planChapters.map((c, i) => ({
          number: c.number || i + 1,
          title: c.title || "",
          summary: c.summary || "",
        }));
        await this.api(`/api/volumes/${this.currentVolume.id}/chapter-plan`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: { chapters } }),
        });
        await this.refreshProject();
      } catch (e) {
        this.error = e.message;
      } finally {
        this.saving = false;
      }
    },

    // ---- 章节 ----
    selectChapter(c) {
      this.currentChapter = { ...c };
    },

    async saveChapter() {
      if (!this.currentChapter) return;
      this.error = "";
      this.saving = true;
      try {
        await this.api(`/api/chapters/${this.currentChapter.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: this.currentChapter.title,
            content: this.currentChapter.content,
          }),
        });
        await this.refreshProject();
      } catch (e) {
        this.error = e.message;
      } finally {
        this.saving = false;
      }
    },

    async confirmChapter() {
      if (!this.currentChapter) return;
      this.error = "";
      this.saving = true;
      try {
        await this.api(`/api/chapters/${this.currentChapter.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "confirmed" }),
        });
        await this.refreshProject();
      } catch (e) {
        this.error = e.message;
      } finally {
        this.saving = false;
      }
    },

    async generateNextChapter() {
      if (this.streaming || !this.currentVolume) return;
      this.error = "";
      this.streaming = true;
      this.liveContent = "";
      try {
        const doneId = await this.runStream(`/api/volumes/${this.currentVolume.id}/chapters`);
        await this.refreshProject();
        if (doneId && this.currentVolume) {
          const ch = (this.currentVolume.chapters || []).find((c) => c.id === doneId);
          if (ch) this.selectChapter(ch);
        }
      } catch (e) {
        this.error = e.message;
      } finally {
        this.streaming = false;
        this.liveContent = "";
      }
    },

    async regenerateChapter() {
      if (!this.currentChapter || this.streaming) return;
      this.error = "";
      this.streaming = true;
      this.liveContent = "";
      try {
        await this.runStream(`/api/chapters/${this.currentChapter.id}/regenerate`);
        await this.refreshProject();
        const fresh = (this.currentVolume.chapters || []).find(
          (c) => c.id === this.currentChapter.id
        );
        if (fresh) this.currentChapter = { ...fresh };
      } catch (e) {
        this.error = e.message;
      } finally {
        this.streaming = false;
        this.liveContent = "";
      }
    },

    async runStream(url) {
      const resp = await fetch(url, { method: "POST" });
      if (!resp.ok) {
        let detail = resp.statusText;
        try {
          const j = await resp.json();
          detail = j.detail || detail;
        } catch (e) {}
        throw new Error(detail);
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let doneChapterId = null;
      let errMsg = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf("\n\n")) >= 0) {
          const raw = buffer.slice(0, idx).trim();
          buffer = buffer.slice(idx + 2);
          for (const line of raw.split("\n")) {
            if (!line.startsWith("data: ")) continue;
            let evt;
            try {
              evt = JSON.parse(line.slice(6));
            } catch (e) {
              continue;
            }
            if (evt.type === "token") this.liveContent += evt.content;
            else if (evt.type === "done") doneChapterId = evt.chapter.id;
            else if (evt.type === "error") errMsg = evt.message;
          }
        }
      }
      if (errMsg) throw new Error(errMsg);
      return doneChapterId;
    },

    // ---- 导出 ----
    async exportVolume() {
      if (!this.currentVolume) return;
      try {
        const data = await this.api(`/api/volumes/${this.currentVolume.id}/export`);
        this.downloadMarkdown(
          data.markdown,
          `${this.project.title || "novel"}·${this.currentVolume.title}.md`
        );
      } catch (e) {
        this.error = e.message;
      }
    },

    async exportMarkdown() {
      try {
        const data = await this.api(`/api/projects/${this.project.id}/export`);
        this.downloadMarkdown(data.markdown, `${this.project.title || "novel"}.md`);
      } catch (e) {
        this.error = e.message;
      }
    },

    downloadMarkdown(text, filename) {
      const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    },
  },
}).mount("#app");
