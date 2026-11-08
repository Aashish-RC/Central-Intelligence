const express = require('express');
const { v4 } = require('uuid');
const { FileSources, FileContext } = require('librechat-data-provider');
const { createImageHandlers } = require('@librechat/api');
const { getStrategyFunctions } = require('~/server/services/Files/strategies');
const db = require('~/models');
const { requireJwtAuth } = require('~/server/middleware');

const router = express.Router();

const saveImageBuffer = async ({ userId, buffer, fileName, mimeType, tenantId }) => {
  const file_id = v4();
  const filename = `${file_id}-${fileName}`;
  const source = FileSources.local;
  const { saveBuffer } = getStrategyFunctions(source);
  const filepath = await saveBuffer({
    userId,
    fileName: filename,
    buffer,
    tenantId,
  });

  await db.createFile(
    {
      user: userId,
      file_id,
      filename,
      filepath,
      bytes: buffer.length,
      type: mimeType,
      context: FileContext.image_generation,
      source,
      tenantId,
    },
    true,
  );

  return {
    file_id,
    filepath,
    filename,
  };
};

const handlers = createImageHandlers({ saveImageBuffer });

router.post('/generate', requireJwtAuth, handlers.generate);
router.get('/config', requireJwtAuth, handlers.getConfig);

module.exports = router;
