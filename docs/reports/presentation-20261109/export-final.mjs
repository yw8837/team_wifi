import fs from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

const root = 'E:/Team_Wifi/';
const workspaceDir = root + 'artifacts/presentation-final-20261109';
const outputDir = root + 'output/presentation-20261109';
const runtime = 'C:/Users/최용우/.cache/codex-runtimes/codex-primary-runtime/dependencies';
process.env.RUNTIME_NODE_MODULES = runtime + '/node/node_modules';
const skill = 'C:/Users/최용우/.codex/plugins/cache/openai-primary-runtime/presentations/26.1104.22356/skills/presentations';
const { Presentation, PresentationFile } = await import(pathToFileURL(runtime + '/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs').href);
const { finalizePresentation } = await import(pathToFileURL(skill + '/container_tools/artifact_tool_utils.mjs').href);

await fs.mkdir(outputDir, { recursive: true });
const proto = JSON.parse(await fs.readFile(workspaceDir + '/deck-proto.json', 'utf8'));
const presentation = Presentation.load(proto);
const imageSources = [
  [0, 0, 'artifacts/presentation-20261109/store-icon-512.png'],
  [9, 0, 'artifacts/account-switch-20261109/chat-compact-live.png'],
  [10, 0, 'artifacts/account-switch-20261109/device-saved-confirmed.png'],
  [10, 1, 'artifacts/account-switch-20261109/web-after-device-remove.png'],
  [21, 0, 'artifacts/handoff-20261109/web-home.png'],
  [22, 0, 'artifacts/community-20261109/mobile-comments.png'],
];
for (const [slideIndex, imageIndex, imagePath] of imageSources) {
  const bytes = await fs.readFile(root + imagePath);
  presentation.slides.getItem(slideIndex).images.items[imageIndex].replace({ blob: bytes, contentType: 'image/png' });
}
const candidatePath = workspaceDir + '/candidate.pptx';
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);
console.log('PPTX exported', presentation.slides.items.length);
const result = await finalizePresentation({
  workspaceDir: root,
  candidatePath,
  finalPath: outputDir + '/모두의육아_중간발표_평가기준반영_20261109.pptx',
  pythonExecutable: runtime + '/python/python.exe',
  integrityValidatorPath: skill + '/container_tools/inspect_presentation_package_integrity.py',
  layoutValidatorPath: skill + '/container_tools/inspect_presentation_layout_geometry.py',
  layoutArgs: ['--expected-slide-size-emu', '12192000,6858000', '--validate-bullet-geometry', '--validate-heading-fit', ...[4, 6, 7, 14, 35, 36].flatMap(n => ['--require-native-table-slide', String(n)])],
  explicitTotalSlideCount: 36,
  requiredNativeTableOwnerSlides: [4, 6, 7, 14, 35, 36],
  requiredNativeChartOwnerSlides: [5, 16],
  materializeLiteralChartWorkbooks: true,
  fontPolicy: { basis: 'design', families: ['Malgun Gothic', 'Arial'] },
  verifyArtifactToolImport: true,
  receiptPath: workspaceDir + '/final-validation.json',
});
console.log(JSON.stringify(result, null, 2));
