/**
 * WiseCrypto - Helpers de criptografia E2E para upload/download de arquivos
 *
 * Fluxo de upload:
 *  1. Gera chave AES-256-GCM via Web Crypto
 *  2. Criptografa o arquivo com essa chave
 *  3. Exporta a chave AES como base64 (futuramente: cifrada com PGP do usuário)
 *  4. Retorna blob criptografado + metadados
 *
 * Fluxo de download:
 *  1. Recebe blob criptografado + chave AES base64 + IV
 *  2. Importa a chave AES
 *  3. Decifra o arquivo
 *  4. Retorna blob original
 */
const WiseCrypto = {

    /**
     * Criptografa um ArrayBuffer com AES-256-GCM
     * @param {ArrayBuffer} plainBuffer - Dados originais do arquivo
     * @returns {Promise<{encryptedBlob: Blob, aesKeyBase64: string, iv: string}>}
     */
    async encryptFile(plainBuffer) {
        const key = await crypto.subtle.generateKey(
            { name: 'AES-GCM', length: 256 },
            true,
            ['encrypt', 'decrypt']
        );

        const iv = crypto.getRandomValues(new Uint8Array(12));

        const cipherBuffer = await crypto.subtle.encrypt(
            { name: 'AES-GCM', iv },
            key,
            plainBuffer
        );

        const rawKey = await crypto.subtle.exportKey('raw', key);
        const aesKeyBase64 = bufferToBase64(rawKey);
        const ivBase64 = bufferToBase64(iv);

        return {
            encryptedBlob: new Blob([cipherBuffer], { type: 'application/octet-stream' }),
            aesKeyBase64,
            iv: ivBase64,
        };
    },

    /**
     * Decifra um ArrayBuffer com AES-256-GCM
     * @param {ArrayBuffer} encryptedBuffer - Dados cifrados
     * @param {string} aesKeyBase64 - Chave AES exportada em base64
     * @param {string} ivBase64 - IV em base64
     * @returns {Promise<Blob>}
     */
    async decryptFile(encryptedBuffer, aesKeyBase64, ivBase64) {
        const rawKey = base64ToBuffer(aesKeyBase64);
        const iv = base64ToBuffer(ivBase64);

        const key = await crypto.subtle.importKey(
            'raw',
            rawKey,
            { name: 'AES-GCM', length: 256 },
            false,
            ['decrypt']
        );

        const plainBuffer = await crypto.subtle.decrypt(
            { name: 'AES-GCM', iv },
            key,
            encryptedBuffer
        );

        return new Blob([plainBuffer]);
    },

    /**
     * Gera par de chaves PGP para o usuário (para futura cifragem da chave AES)
     * @param {string} name
     * @param {string} email
     * @param {string} passphrase
     * @returns {Promise<{publicKey: string, privateKey: string}>}
     */
    async generatePGPKeyPair(name, email, passphrase) {
        if (typeof openpgp === 'undefined') {
            throw new Error('OpenPGP.js não carregado');
        }
        const { privateKey, publicKey } = await openpgp.generateKey({
            type: 'ecc',
            curve: 'curve25519',
            userIDs: [{ name, email }],
            passphrase,
            format: 'armored',
        });
        return { publicKey, privateKey };
    },

    /**
     * Cifra a chave AES com a chave pública PGP do destinatário
     * @param {string} aesKeyBase64
     * @param {string} publicKeyArmored
     * @returns {Promise<string>} Mensagem PGP cifrada (armored)
     */
    async encryptKeyWithPGP(aesKeyBase64, publicKeyArmored) {
        if (typeof openpgp === 'undefined') {
            throw new Error('OpenPGP.js não carregado');
        }
        const pubKey = await openpgp.readKey({ armoredKey: publicKeyArmored });
        const encrypted = await openpgp.encrypt({
            message: await openpgp.createMessage({ text: aesKeyBase64 }),
            encryptionKeys: pubKey,
        });
        return encrypted;
    },

    /**
     * Decifra a chave AES com a chave privada PGP do usuário
     * @param {string} encryptedMessage - Mensagem PGP cifrada (armored)
     * @param {string} privateKeyArmored
     * @param {string} passphrase
     * @returns {Promise<string>} Chave AES em base64
     */
    async decryptKeyWithPGP(encryptedMessage, privateKeyArmored, passphrase) {
        if (typeof openpgp === 'undefined') {
            throw new Error('OpenPGP.js não carregado');
        }
        const privKey = await openpgp.decryptKey({
            privateKey: await openpgp.readPrivateKey({ armoredKey: privateKeyArmored }),
            passphrase,
        });
        const message = await openpgp.readMessage({ armoredMessage: encryptedMessage });
        const { data } = await openpgp.decrypt({
            message,
            decryptionKeys: privKey,
        });
        return data;
    },
};

/* ---- Base64 <-> ArrayBuffer helpers ---- */

function bufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
}

function base64ToBuffer(base64) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
}
